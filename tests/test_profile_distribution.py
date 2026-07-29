"""Offline contract tests for the supported Non-Profit Hermes distribution."""
from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
import yaml

from hermes_cli.profile_distribution import (
    DistributionError,
    install_distribution,
    read_manifest,
    update_distribution,
)


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_COMMANDS = ("daily", "need", "donation", "report", "task", "inventory", "event")
EXPECTED_OWNED_PATHS = (
    "distribution.yaml",
    "SOUL.md",
    "config.yaml",
    "skills/non-profit-hermes",
    "plugins/non-profit-hermes",
)
EXPECTED_ENV = {
    "TELEGRAM_BOT_TOKEN": True,
    "TELEGRAM_ALLOWED_USERS": True,
    "NON_PROFIT_HERMES_CREDENTIALS_FILE": True,
    "NON_PROFIT_HERMES_SPREADSHEET_ID": True,
    "NON_PROFIT_HERMES_CALENDAR_ID": False,
    "NON_PROFIT_HERMES_CONFIG_DIR": False,
    "DATA_DIR": False,
    "STATE_DIR": False,
    "PUBLIC_DIR": False,
    "TELEGRAM_SOURCE_SCOPE": False,
    "TELEGRAM_HOME_CHANNEL": False,
}
LEGACY_PLUGINS = (
    "non-profit-hermes-daily",
    "non-profit-hermes-need",
    "non-profit-hermes-donation",
    "non-profit-hermes-report",
    "non-profit-hermes-task",
    "non-profit-hermes-inventory",
    "non-profit-hermes-event",
)


def load_yaml(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


@pytest.fixture()
def isolated_profiles(tmp_path: Path, monkeypatch) -> Path:
    from hermes_cli import profiles

    default_home = tmp_path / "hermes-home"
    profile_root = default_home / "profiles"
    default_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(default_home))
    monkeypatch.setattr(profiles, "get_profile_dir", lambda name: profile_root / name)
    return default_home


def copy_distribution_source(destination: Path) -> Path:
    destination.mkdir()
    for filename in ("distribution.yaml", "SOUL.md", "config.yaml"):
        shutil.copy2(ROOT / filename, destination / filename)
    shutil.copytree(
        ROOT / "skills" / "non-profit-hermes",
        destination / "skills" / "non-profit-hermes",
    )
    shutil.copytree(
        ROOT / "plugins" / "non-profit-hermes",
        destination / "plugins" / "non-profit-hermes",
    )
    return destination


class FakePluginContext:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def register_command(self, name, handler, description="", args_hint="") -> None:
        self.commands.append(name)


def load_installed_plugin(plugin_root: Path):
    module_name = f"installed_nonprofit_plugin_{plugin_root.parent.parent.name}"
    spec = importlib.util.spec_from_file_location(
        module_name,
        plugin_root / "__init__.py",
        submodule_search_locations=[str(plugin_root)],
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_uses_exact_supported_v1_contract() -> None:
    raw = load_yaml(ROOT / "distribution.yaml")
    assert set(raw) == {
        "name",
        "version",
        "description",
        "hermes_requires",
        "author",
        "license",
        "env_requires",
        "distribution_owned",
    }

    manifest = read_manifest(ROOT)
    assert manifest is not None
    assert manifest.name == "nonprofit"
    assert manifest.version == "1.0.0"
    assert manifest.description
    assert manifest.hermes_requires == ">=0.18.2"
    assert manifest.author == "falloutmule"
    assert manifest.license == "MIT"
    assert tuple(manifest.owned_paths()) == EXPECTED_OWNED_PATHS

    assert [requirement.name for requirement in manifest.env_requires] == list(EXPECTED_ENV)
    assert {
        requirement.name: requirement.required for requirement in manifest.env_requires
    } == EXPECTED_ENV
    assert all(requirement.description for requirement in manifest.env_requires)
    assert all(requirement.default is None for requirement in manifest.env_requires)
    assert all(set(entry) == {"name", "description", "required"} for entry in raw["env_requires"])

    package = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    plugin = load_yaml(ROOT / "plugins" / "non-profit-hermes" / "plugin.yaml")
    assert package["project"]["version"] == plugin["version"] == manifest.version


def test_config_contains_only_supported_safe_defaults() -> None:
    assert load_yaml(ROOT / "config.yaml") == {
        "model": "openai-codex/gpt-5.6-sol",
        "compression": {"enabled": True},
        "context": {"engine": "compressor"},
        "privacy": {"redact_pii": True},
        "security": {"redact_secrets": True},
        "plugins": {
            "enabled": ["non-profit-hermes"],
            "disabled": list(LEGACY_PLUGINS),
        },
    }


def test_soul_defines_sanitized_operational_boundaries() -> None:
    soul = (ROOT / "SOUL.md").read_text(encoding="utf-8")
    lowered = soul.lower()

    assert soul.startswith("# Non-Profit Hermes")
    assert all(f"/{command}" in soul for command in EXPECTED_COMMANDS)
    assert all(
        classification in lowered
        for classification in ("private", "internal", "board-visible", "public-safe")
    )
    assert "draft" in lowered
    assert "/daily" in soul and "read-only" in lowered
    assert "calendar" in lowered and "one-shot" in lowered and "authorization" in lowered
    assert "publication" in lowered and "approval" in lowered
    assert "unknown" in lowered and "do not invent" in lowered
    assert "C:/Users/" not in soul and "C:\\Users\\" not in soul
    assert "gateway is running" not in lowered and "gateway is stopped" not in lowered


def test_bundled_skill_has_valid_frontmatter_and_safe_command_guidance() -> None:
    skill_path = ROOT / "skills" / "non-profit-hermes" / "SKILL.md"
    content = skill_path.read_text(encoding="utf-8")
    assert content.startswith("---\n")
    frontmatter_text, body = content[4:].split("\n---\n", 1)
    frontmatter = yaml.safe_load(frontmatter_text)

    assert frontmatter == {
        "name": "non-profit-hermes",
        "description": (
            "Use when operating the seven-command Non-Profit Hermes workflow. "
            "Keeps intake draft-first, privacy-classified, approval-gated, and auditable."
        ),
        "version": "1.0.0",
        "author": "Hermes Agent",
        "license": "MIT",
        "metadata": {
            "hermes": {
                "tags": ["nonprofit", "telegram", "privacy", "approvals", "audit"],
                "related_skills": [],
            }
        },
    }
    assert len(frontmatter["description"]) <= 1024
    assert body.strip()
    assert all(f"/{command}" in body for command in EXPECTED_COMMANDS)
    assert "## Completion Checks" in body
    assert "credential setup" not in body.lower()
    assert "C:/Users/" not in body and "C:\\Users\\" not in body


def test_gitignore_covers_profile_state_and_keeps_distribution_authored() -> None:
    ignored = {
        line.strip()
        for line in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert {
        "auth.json",
        ".env",
        ".env.EXAMPLE",
        "state.db",
        "state.db-shm",
        "state.db-wal",
        "hermes_state.db",
        "response_store.db",
        "response_store.db-shm",
        "response_store.db-wal",
        "gateway.pid",
        "gateway_state.json",
        "processes.json",
        "auth.lock",
        "active_profile",
        ".update_check",
        "errors.log",
        ".hermes_history",
        "memories/",
        "sessions/",
        "logs/",
        "plans/",
        "workspace/",
        "home/",
        "image_cache/",
        "audio_cache/",
        "document_cache/",
        "browser_screenshots/",
        "checkpoints/",
        "sandboxes/",
        "backups/",
        "cache/",
        "hermes-agent/",
        ".worktrees/",
        "profiles/",
        "bin/",
        "node_modules/",
        "local/",
        "__pycache__/",
        "*.py[cod]",
        ".pytest_cache/",
        "build/",
        "dist/",
        "*.egg-info/",
    } <= ignored

    authored = (
        "distribution.yaml",
        "SOUL.md",
        "config.yaml",
        "skills/non-profit-hermes/SKILL.md",
        "plugins/non-profit-hermes/plugin.yaml",
    )
    for relative in authored:
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", relative],
            cwd=ROOT,
            capture_output=True,
            check=False,
            text=True,
        )
        assert result.returncode == 1, (relative, result.stdout, result.stderr)


def test_isolated_install_copies_profile_payload_and_registers_seven_commands(
    isolated_profiles: Path,
    tmp_path: Path,
) -> None:
    source = copy_distribution_source(tmp_path / "distribution-source")
    (source / ".env").write_text("MUST_NOT_COPY=private\n", encoding="utf-8")
    (source / "auth.json").write_text("private\n", encoding="utf-8")
    (source / "state.db").write_text("private\n", encoding="utf-8")
    (source / "gateway.pid").write_text("private\n", encoding="utf-8")
    (source / "memories").mkdir()
    (source / "memories" / "MEMORY.md").write_text("private\n", encoding="utf-8")

    plan = install_distribution(str(source), name="nonprofit-v1-test")
    target = isolated_profiles / "profiles" / "nonprofit-v1-test"
    assert plan.target_dir == target
    assert plan.manifest.name == "nonprofit-v1-test"
    assert plan.manifest.version == "1.0.0"

    for relative in (
        "SOUL.md",
        "config.yaml",
        "skills/non-profit-hermes/SKILL.md",
        "plugins/non-profit-hermes/plugin.yaml",
        "plugins/non-profit-hermes/__init__.py",
        "plugins/non-profit-hermes/commands.py",
    ):
        assert (target / relative).read_bytes() == (source / relative).read_bytes()

    installed_config = load_yaml(target / "config.yaml")
    assert installed_config["plugins"]["enabled"] == ["non-profit-hermes"]
    assert installed_config["plugins"]["disabled"] == list(LEGACY_PLUGINS)

    env_example = (target / ".env.EXAMPLE").read_text(encoding="utf-8")
    assert all(name in env_example for name in EXPECTED_ENV)
    assert all(
        not line.split("=", 1)[1]
        for line in env_example.splitlines()
        if "=" in line and not line.lstrip().startswith("#")
    )

    assert not (target / ".env").exists()
    assert not (target / "auth.json").exists()
    assert not (target / "state.db").exists()
    assert not (target / "gateway.pid").exists()
    assert not (target / "gateway_state.json").exists()
    assert not (target / "processes.json").exists()
    assert not any((target / "memories").iterdir())
    assert not (isolated_profiles / "config.yaml").exists()
    assert not (isolated_profiles / "plugins").exists()

    plugin = load_installed_plugin(target / "plugins" / "non-profit-hermes")
    context = FakePluginContext()
    plugin.register(context)
    plugin.register(context)
    assert context.commands == list(EXPECTED_COMMANDS)


def test_existing_profile_collision_fails_without_force(
    isolated_profiles: Path,
    tmp_path: Path,
) -> None:
    source = copy_distribution_source(tmp_path / "distribution-source")
    install_distribution(str(source), name="nonprofit-v1-test")

    with pytest.raises(DistributionError, match="already exists"):
        install_distribution(str(source), name="nonprofit-v1-test")


def seed_user_state(target: Path) -> dict[str, bytes]:
    state = {
        ".env": b"USER_ENV=preserve\n",
        "auth.json": b"user-auth\n",
        "memories/MEMORY.md": b"user-memory\n",
        "sessions/session.json": b"user-session\n",
        "state.db": b"user-state\n",
        "logs/gateway.log": b"user-log\n",
        "local/override.txt": b"user-local\n",
    }
    for relative, content in state.items():
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return state


def assert_user_state(target: Path, state: dict[str, bytes]) -> None:
    for relative, content in state.items():
        assert (target / relative).read_bytes() == content


def test_update_refreshes_owned_files_and_preserves_user_data_and_config(
    isolated_profiles: Path,
    tmp_path: Path,
) -> None:
    source = copy_distribution_source(tmp_path / "distribution-source")
    plan = install_distribution(str(source), name="nonprofit-v1-test")
    target = plan.target_dir
    state = seed_user_state(target)
    user_config = b"model: user-selected-model\n"
    (target / "config.yaml").write_bytes(user_config)

    updated_soul = (source / "SOUL.md").read_bytes() + b"\nUpdate marker.\n"
    updated_skill = (
        source / "skills" / "non-profit-hermes" / "SKILL.md"
    ).read_bytes() + b"\nUpdate marker.\n"
    updated_plugin = (
        source / "plugins" / "non-profit-hermes" / "commands.py"
    ).read_bytes() + b"\n# update marker\n"
    (source / "SOUL.md").write_bytes(updated_soul)
    (source / "skills" / "non-profit-hermes" / "SKILL.md").write_bytes(updated_skill)
    (source / "plugins" / "non-profit-hermes" / "commands.py").write_bytes(updated_plugin)
    (source / "config.yaml").write_text(
        "model: distribution-updated-model\n", encoding="utf-8"
    )

    update_distribution("nonprofit-v1-test", force_config=False)

    assert (target / "SOUL.md").read_bytes() == updated_soul
    assert (
        target / "skills" / "non-profit-hermes" / "SKILL.md"
    ).read_bytes() == updated_skill
    assert (
        target / "plugins" / "non-profit-hermes" / "commands.py"
    ).read_bytes() == updated_plugin
    assert (target / "config.yaml").read_bytes() == user_config
    assert_user_state(target, state)

    update_distribution("nonprofit-v1-test", force_config=True)

    assert load_yaml(target / "config.yaml") == {"model": "distribution-updated-model"}
    assert_user_state(target, state)


def test_force_install_replaces_owned_files_but_preserves_user_state(
    isolated_profiles: Path,
    tmp_path: Path,
) -> None:
    source = copy_distribution_source(tmp_path / "distribution-source")
    plan = install_distribution(str(source), name="nonprofit-v1-test")
    target = plan.target_dir
    state = seed_user_state(target)

    updated_soul = b"# Non-Profit Hermes force-install marker\n"
    (source / "SOUL.md").write_bytes(updated_soul)
    (source / "config.yaml").write_text("model: force-install-model\n", encoding="utf-8")

    install_distribution(str(source), name="nonprofit-v1-test", force=True)

    assert (target / "SOUL.md").read_bytes() == updated_soul
    assert load_yaml(target / "config.yaml") == {"model": "force-install-model"}
    assert_user_state(target, state)


def test_failed_update_preflight_leaves_prior_owned_state_unchanged(
    isolated_profiles: Path,
    tmp_path: Path,
) -> None:
    source = copy_distribution_source(tmp_path / "distribution-source")
    plan = install_distribution(str(source), name="nonprofit-v1-test")
    target = plan.target_dir
    tracked = (
        "distribution.yaml",
        "SOUL.md",
        "config.yaml",
        "skills/non-profit-hermes/SKILL.md",
        "plugins/non-profit-hermes/plugin.yaml",
        "plugins/non-profit-hermes/__init__.py",
        "plugins/non-profit-hermes/commands.py",
    )
    before = {relative: (target / relative).read_bytes() for relative in tracked}

    manifest = load_yaml(source / "distribution.yaml")
    manifest["hermes_requires"] = ">=99.0.0"
    (source / "distribution.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )
    (source / "SOUL.md").write_text("must-not-apply\n", encoding="utf-8")

    with pytest.raises(DistributionError, match="requires Hermes"):
        update_distribution("nonprofit-v1-test")

    assert {relative: (target / relative).read_bytes() for relative in tracked} == before


def test_authored_and_installed_payloads_have_no_secret_literals_or_private_paths(
    isolated_profiles: Path,
    tmp_path: Path,
) -> None:
    source = copy_distribution_source(tmp_path / "distribution-source")
    target = install_distribution(str(source), name="nonprofit-v1-test").target_dir
    relative_files = (
        "distribution.yaml",
        "SOUL.md",
        "config.yaml",
        "skills/non-profit-hermes/SKILL.md",
        "plugins/non-profit-hermes/plugin.yaml",
        "plugins/non-profit-hermes/__init__.py",
        "plugins/non-profit-hermes/commands.py",
    )
    patterns = (
        re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{30,}\b"),
        re.compile(r"\bya29\.[A-Za-z0-9_-]+"),
        re.compile(r"\b1//[A-Za-z0-9_-]+"),
        re.compile(r"C:/Users/", re.IGNORECASE),
        re.compile(r"C:\\\\Users\\\\", re.IGNORECASE),
        re.compile(r"/Users/[^/\s]+/"),
    )

    for relative in relative_files:
        authored = (source / relative).read_text(encoding="utf-8")
        installed = (target / relative).read_text(encoding="utf-8")
        if relative == "distribution.yaml":
            installed_manifest = yaml.safe_load(installed)
            installed_manifest.pop("source", None)
            installed_manifest.pop("installed_at", None)
            installed = yaml.safe_dump(installed_manifest, sort_keys=False)
        assert all(not pattern.search(authored) for pattern in patterns), relative
        assert all(not pattern.search(installed) for pattern in patterns), relative


def test_documentation_covers_supported_distribution_lifecycle_without_live_claims() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    operations = (ROOT / "OPERATIONS.md").read_text(encoding="utf-8")
    development = (ROOT / "DEVELOPMENT.md").read_text(encoding="utf-8")
    report = (
        ROOT / "reports" / "v1.0.0" / "PROFILE_DISTRIBUTION_REPORT.md"
    ).read_text(encoding="utf-8")
    combined = "\n".join((readme, operations, development, report))

    assert "python -m pip install ." in readme
    assert "python -m pip install \"git+https://github.com/falloutmule/non-profit-hermes-mvp.git@v1.0.0\"" in readme
    assert "hermes profile install . --name nonprofit" in readme
    assert "hermes profile install https://github.com/falloutmule/non-profit-hermes-mvp.git --name nonprofit" in readme
    assert "hermes profile info nonprofit" in combined
    assert "hermes -p nonprofit auth add openai-codex" in operations
    assert "hermes profile update nonprofit" in operations
    assert "--force-config" in operations
    assert "hermes profile delete nonprofit" in operations
    assert "doctor is a downstream" in operations.lower()
    assert "does not install the Python package" in combined
    assert "does not start the gateway" in combined
    assert "profile/" in development and "unsupported" in development.lower()
    assert all(heading in report for heading in ("## RED", "## GREEN", "## Verification", "## Limitations"))
    assert "No live profile" in report
