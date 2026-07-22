"""Offline tests for the fail-closed clean-install acceptance harness."""
from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from io import StringIO

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "clean_install_acceptance.py"
EXPECTED_COMMANDS = ("daily", "need", "donation", "report", "task", "inventory", "event")


def load_harness():
    spec = importlib.util.spec_from_file_location("clean_install_acceptance", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AdmissionRunner:
    def __init__(self, source: Path) -> None:
        self.source = source.resolve()
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, argv, **kwargs):
        harness = load_harness()
        command = tuple(str(value) for value in argv)
        self.calls.append(command)
        if command[:3] == ("git", "-C", str(self.source)):
            operation = command[3:]
            if operation == ("rev-parse", "--show-toplevel"):
                return harness.CommandResult(0, str(self.source) + "\n", "")
            if operation == ("rev-parse", "HEAD"):
                return harness.CommandResult(0, "a" * 40 + "\n", "")
            if operation == ("status", "--porcelain=v1", "--untracked-files=all"):
                return harness.CommandResult(0, "", "")
        if command == ("hermes", "profile", "install", "--help"):
            return harness.CommandResult(0, "usage: hermes profile install SOURCE --name NAME -y\n", "")
        raise AssertionError(f"unexpected command: {command!r}")


def test_admission_accepts_only_clean_git_source_and_disposable_roots(tmp_path: Path) -> None:
    harness = load_harness()
    source = tmp_path / "source"
    source.mkdir()
    cache_root = tmp_path / "hermes" / "cache"
    cache_root.mkdir(parents=True)
    output = cache_root / "clean-install-001"
    active_root = tmp_path / "hermes"
    runner = AdmissionRunner(source)

    admission = harness.validate_admission(
        source=source,
        output_root=output,
        profile="nonprofit-v1-test-001",
        allowed_cache_root=cache_root,
        active_hermes_root=active_root,
        existing_profile_names={"default", "nonprofit", "builder-grok"},
        runner=runner,
    )

    assert admission.source == source.resolve()
    assert admission.output_root == output.resolve()
    assert admission.source_head == "a" * 40
    assert admission.profile == "nonprofit-v1-test-001"
    assert admission.isolated_hermes_root == output.resolve() / "platform" / "hermes"
    assert not output.exists()
    assert runner.calls == [
        ("git", "-C", str(source.resolve()), "rev-parse", "--show-toplevel"),
        ("git", "-C", str(source.resolve()), "rev-parse", "HEAD"),
        ("git", "-C", str(source.resolve()), "status", "--porcelain=v1", "--untracked-files=all"),
        ("hermes", "profile", "install", "--help"),
    ]


def test_safe_archive_extraction_rejects_traversal_without_partial_output(
    tmp_path: Path,
) -> None:
    harness = load_harness()
    archive = tmp_path / "source.tar"
    with tarfile.open(archive, "w") as bundle:
        safe = tarfile.TarInfo("README.md")
        safe_bytes = b"safe\n"
        safe.size = len(safe_bytes)
        bundle.addfile(safe, io.BytesIO(safe_bytes))
        escaped = tarfile.TarInfo("../escaped.txt")
        escaped_bytes = b"must-not-write\n"
        escaped.size = len(escaped_bytes)
        bundle.addfile(escaped, io.BytesIO(escaped_bytes))

    destination = tmp_path / "extracted"
    with pytest.raises(harness.HarnessError) as failure:
        harness.safe_extract_archive(archive, destination)

    assert failure.value.code == "ARCHIVE_UNSAFE_PATH"
    assert not destination.exists()
    assert not (tmp_path / "escaped.txt").exists()


def test_privacy_scan_returns_only_deterministic_codes_and_counts(tmp_path: Path) -> None:
    harness = load_harness()
    tree = tmp_path / "tree"
    (tree / "memories").mkdir(parents=True)
    (tree / ".env").write_text("TOKEN=private-value\n", encoding="utf-8")
    (tree / "auth.json").write_text('{"token":"auth-private"}\n', encoding="utf-8")
    (tree / "memories" / "MEMORY.md").write_text("private memory\n", encoding="utf-8")
    # Assemble scanner sentinels at runtime so the clean source archive does
    # not itself contain a token-shaped or raw private-ID literal.
    secret_values = (
        "".join(("123456789", ":", "A" * 32)),
        "".join(("ya", "29.", "A" * 24)),
        "".join(("-", "100", "1234567890")),
    )
    (tree / "safe.txt").write_text("\n".join(secret_values), encoding="utf-8")

    findings = harness.scan_private_material(tree)
    serialized = json.dumps(findings, sort_keys=True)

    assert findings == {
        "AUTH_FILE": 1,
        "DOTENV_FILE": 1,
        "MEMORY_PATH": 1,
        "RAW_GOOGLE_TOKEN": 1,
        "RAW_TELEGRAM_BOT_TOKEN": 1,
        "RAW_TELEGRAM_PRIVATE_ID": 1,
    }
    assert all(value not in serialized for value in secret_values)
    assert "private-value" not in serialized
    assert "safe.txt" not in serialized


def test_privacy_scan_excludes_only_test_fixture_literals_not_test_private_paths(
    tmp_path: Path,
) -> None:
    harness = load_harness()
    tree = tmp_path / "tree"
    tests = tree / "tests"
    tests.mkdir(parents=True)
    synthetic_token = "".join(("123456789", ":", "A" * 32))
    (tests / "fixture.py").write_text(repr(synthetic_token), encoding="utf-8")

    assert harness.scan_private_material(tree) == {}

    (tests / "auth.json").write_text("{}\n", encoding="utf-8")
    assert harness.scan_private_material(tree) == {"AUTH_FILE": 1}


def test_isolated_environment_and_command_plan_never_select_host_profile(
    tmp_path: Path,
) -> None:
    harness = load_harness()
    output = (tmp_path / "cache" / "run-001").resolve()
    admission = harness.Admission(
        source=(tmp_path / "source").resolve(),
        output_root=output,
        profile="nonprofit-v1-test-001",
        source_head="b" * 40,
        allowed_cache_root=(tmp_path / "cache").resolve(),
        active_hermes_root=(tmp_path / "active-hermes").resolve(),
        isolated_hermes_root=output / "platform" / "hermes",
    )
    inherited = {
        "PATH": "host-path",
        "PATHEXT": ".EXE",
        "SYSTEMROOT": "C:/Windows",
        "HERMES_PROFILE": "nonprofit",
        "HERMES_ACTIVE_PROFILE": "default",
        "TELEGRAM_BOT_TOKEN": "host-secret",
        "GOOGLE_APPLICATION_CREDENTIALS": "host-google-secret",
    }

    environment, synthetic_values = harness.build_isolated_environment(admission, inherited)
    plan = harness.build_command_plan(
        admission,
        extracted=output / "source",
        install_source=output / "profile-install-source",
        wheel=output / "artifacts" / "non_profit_hermes-1.0.0-py3-none-any.whl",
        venv_python=output / "venv" / "Scripts" / "python.exe",
        console=output / "venv" / "Scripts" / "nonprofit-hermes.exe",
        external_cwd=output / "work",
    )

    assert environment["PATH"] == "host-path"
    assert environment["LOCALAPPDATA"] == str(output / "platform")
    assert environment["HOME"] == environment["USERPROFILE"] == str(output / "home")
    assert environment["HERMES_HOME"] == str(output / "platform" / "hermes")
    assert "HERMES_PROFILE" not in environment
    assert "HERMES_ACTIVE_PROFILE" not in environment
    assert "TELEGRAM_BOT_TOKEN" not in environment
    assert "GOOGLE_APPLICATION_CREDENTIALS" not in environment
    assert synthetic_values == {}
    assert plan["profile_install"] == (
        "hermes",
        "profile",
        "install",
        str(output / "profile-install-source"),
        "--name",
        "nonprofit-v1-test-001",
        "-y",
    )
    assert plan["doctor_module"][-5:] == (
        "--profile",
        "nonprofit-v1-test-001",
        "--offline",
        "--strict",
        "--json",
    )
    assert plan["doctor_console"][1:] == (
        "doctor",
        "--profile",
        "nonprofit-v1-test-001",
        "--offline",
        "--strict",
        "--json",
    )
    assert all(isinstance(argv, tuple) for argv in plan.values())


def test_doctor_reports_must_match_remain_redacted_and_leave_profile_unchanged(
    tmp_path: Path,
) -> None:
    harness = load_harness()
    profile = tmp_path / "profile"
    profile.mkdir()
    (profile / "config.yaml").write_text("model: synthetic\n", encoding="utf-8")
    before = harness.snapshot_tree(profile)
    payload = {
        "schema_version": 1,
        "mode": "offline",
        "profile": "nonprofit-v1-test-001",
        "strict": True,
        "package_version": "1.0.0",
        "summary": {"pass": 10, "warn": 0, "fail": 0, "skip": 5},
        "checks": [],
        "exit_code": 0,
    }
    module_output = json.dumps(payload, sort_keys=True)
    console_output = json.dumps(payload, separators=(",", ":"))

    summary = harness.verify_doctor_equivalence(
        module_output,
        console_output,
        forbidden_values=("synthetic-secret-value",),
    )

    assert summary == {
        "exit_code": 0,
        "mode": "offline",
        "package_version": "1.0.0",
        "profile": "nonprofit-v1-test-001",
        "summary": {"fail": 0, "pass": 10, "skip": 5, "warn": 0},
    }
    assert harness.snapshot_tree(profile) == before

    leaked = dict(payload)
    leaked["checks"] = [{"message": "synthetic-secret-value"}]
    with pytest.raises(harness.HarnessError) as failure:
        harness.verify_doctor_equivalence(
            json.dumps(leaked),
            console_output,
            forbidden_values=("synthetic-secret-value",),
        )
    assert failure.value.code == "DOCTOR_SECRET_LEAK"


def test_installed_profile_is_accepted_before_synthetic_files_and_registers_exact_commands(
    tmp_path: Path,
) -> None:
    harness = load_harness()
    profile = tmp_path / "platform" / "hermes" / "profiles" / "nonprofit-v1-test-001"
    plugin = profile / "plugins" / "non-profit-hermes"
    skill = profile / "skills" / "non-profit-hermes"
    plugin.mkdir(parents=True)
    skill.mkdir(parents=True)
    (profile / "distribution.yaml").write_text(
        "name: nonprofit-v1-test-001\n"
        "version: 1.0.0\n"
        "distribution_owned:\n"
        "  - distribution.yaml\n"
        "  - SOUL.md\n"
        "  - config.yaml\n"
        "  - skills/non-profit-hermes\n"
        "  - plugins/non-profit-hermes\n",
        encoding="utf-8",
    )
    (profile / "SOUL.md").write_text("# Non-Profit Hermes\n", encoding="utf-8")
    (profile / "config.yaml").write_text(
        "model: openai-codex/gpt-5.6-sol\n"
        "plugins:\n"
        "  enabled: [non-profit-hermes]\n"
        "  disabled:\n"
        "    - non-profit-hermes-daily\n"
        "    - non-profit-hermes-need\n"
        "    - non-profit-hermes-donation\n"
        "    - non-profit-hermes-report\n"
        "    - non-profit-hermes-task\n"
        "    - non-profit-hermes-inventory\n"
        "    - non-profit-hermes-event\n",
        encoding="utf-8",
    )
    (skill / "SKILL.md").write_text("# safe\n", encoding="utf-8")
    (plugin / "plugin.yaml").write_text(
        "name: non-profit-hermes\nversion: 1.0.0\nkind: standalone\n",
        encoding="utf-8",
    )
    (plugin / "__init__.py").write_text("# safe\n", encoding="utf-8")
    (plugin / "commands.py").write_text("# safe\n", encoding="utf-8")
    (profile / ".env.EXAMPLE").write_text("TELEGRAM_BOT_TOKEN=\n", encoding="utf-8")

    inventory = harness.inspect_installed_profile(profile, "nonprofit-v1-test-001")
    environment = {"PATH": "host-path"}
    forbidden = harness.stage_synthetic_configuration(profile, tmp_path, environment)
    commands = harness.verify_registered_commands(json.dumps(list(EXPECTED_COMMANDS)))

    assert inventory == {
        "auth_absent_before_synthetic": True,
        "gateway_stopped": True,
        "legacy_plugins_absent": True,
        "model_correct": True,
        "owned_paths_correct": True,
        "private_material_absent": True,
        "unified_plugin_present": True,
        "version_correct": True,
    }
    assert not (profile / ".env").exists()
    assert (profile / "auth.json").is_file()
    assert (tmp_path / "synthetic" / "google-credentials.json").is_file()
    assert all("synthetic" in value for value in forbidden)
    assert commands == list(EXPECTED_COMMANDS)


def test_wheel_verifier_requires_exact_package_members_version_and_entrypoint(
    tmp_path: Path,
) -> None:
    harness = load_harness()
    extracted = tmp_path / "source"
    package = extracted / "non_profit_hermes"
    resources = package / "resources"
    resources.mkdir(parents=True)
    (package / "__init__.py").write_text('__version__ = "1.0.0"\n', encoding="utf-8")
    (package / "doctor.py").write_text("def main(): return 0\n", encoding="utf-8")
    (resources / "defaults.toml").write_text('version = "1.0.0"\n', encoding="utf-8")
    wheel = tmp_path / "non_profit_hermes-1.0.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        for relative in (
            "non_profit_hermes/__init__.py",
            "non_profit_hermes/doctor.py",
            "non_profit_hermes/resources/defaults.toml",
        ):
            archive.write(extracted / relative, relative)
        archive.writestr(
            "non_profit_hermes-1.0.0.dist-info/entry_points.txt",
            "[console_scripts]\nnonprofit-hermes = non_profit_hermes.doctor:main\n",
        )
        for name in ("METADATA", "WHEEL", "top_level.txt", "RECORD"):
            archive.writestr(f"non_profit_hermes-1.0.0.dist-info/{name}", "safe\n")

    result = harness.verify_wheel_artifact(wheel, extracted)

    assert result["version"] == "1.0.0"
    assert result["member_count"] == 8
    assert result["console_entrypoint"] is True
    assert len(result["sha256"]) == 64

    with zipfile.ZipFile(wheel, "a") as archive:
        archive.writestr("non_profit_hermes/private-token.json", "private")
    with pytest.raises(harness.HarnessError) as failure:
        harness.verify_wheel_artifact(wheel, extracted)
    assert failure.value.code == "WHEEL_MEMBERS_INVALID"


def test_profile_install_source_is_pristine_and_distinct_from_git_index_tree(
    tmp_path: Path,
) -> None:
    """The tree passed to `hermes profile install` must contain no .git."""
    harness = load_harness()
    # Build a real archive from the candidate commit.
    archive_path = tmp_path / "source.tar"
    result = subprocess.run(
        ["git", "archive", "--format=tar", "--output", str(archive_path), "HEAD"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    # Simulate the Git-index inspection tree: it legitimately gains .git.
    index_tree = tmp_path / "index-tree"
    harness.safe_extract_archive(archive_path, index_tree)
    (index_tree / ".git").mkdir()
    (index_tree / ".git" / "index").write_bytes(b"temporary-index")
    assert (index_tree / ".git").is_dir()

    # The profile-install source must be a distinct, pristine extraction.
    install_source = tmp_path / "profile-install-source"
    evidence = harness.build_profile_install_source(archive_path, install_source)

    assert evidence["git_metadata_absent"] is True
    assert evidence["required_assets_present"] is True
    assert evidence["archive_sha256"] == __import__("hashlib").sha256(
        archive_path.read_bytes()
    ).hexdigest()
    assert not (install_source / ".git").exists()
    for relative in (
        "distribution.yaml",
        "SOUL.md",
        "config.yaml",
        "skills/non-profit-hermes/SKILL.md",
        "plugins/non-profit-hermes/plugin.yaml",
        "plugins/non-profit-hermes/__init__.py",
        "plugins/non-profit-hermes/commands.py",
        "non_profit_hermes/__init__.py",
        "non_profit_hermes/resources/defaults.toml",
    ):
        assert (install_source / relative).is_file(), relative
    # The unchanged classifier must pass the clean tree.
    assert harness.scan_private_material(install_source) == {}


def test_profile_install_source_rejects_collision_and_missing_assets(tmp_path: Path) -> None:
    harness = load_harness()
    archive_path = tmp_path / "source.tar"
    subprocess.run(
        ["git", "archive", "--format=tar", "--output", str(archive_path), "HEAD"],
        cwd=ROOT,
        check=True,
    )
    destination = tmp_path / "taken"
    destination.mkdir()
    with pytest.raises(harness.HarnessError) as failure:
        harness.build_profile_install_source(archive_path, destination)
    assert failure.value.code == "INSTALL_SOURCE_COLLISION"

    # An archive missing required distribution assets must fail closed.
    stripped = tmp_path / "stripped.tar"
    source_only = tmp_path / "only-package"
    (source_only / "non_profit_hermes").mkdir(parents=True)
    (source_only / "non_profit_hermes" / "__init__.py").write_text(
        '__version__ = "1.0.0"\n', encoding="utf-8"
    )
    with tarfile.open(stripped, "w") as bundle:
        bundle.add(source_only / "non_profit_hermes" / "__init__.py", arcname="non_profit_hermes/__init__.py")
    with pytest.raises(harness.HarnessError) as failure:
        harness.build_profile_install_source(stripped, tmp_path / "stripped-out")
    assert failure.value.code == "INSTALL_SOURCE_INCOMPLETE"


def test_command_plan_passes_clean_install_source_to_profile_installer(tmp_path: Path) -> None:
    harness = load_harness()
    output = (tmp_path / "cache" / "run-001").resolve()
    admission = harness.Admission(
        source=(tmp_path / "source").resolve(),
        output_root=output,
        profile="nonprofit-v1-test-001",
        source_head="b" * 40,
        allowed_cache_root=(tmp_path / "cache").resolve(),
        active_hermes_root=(tmp_path / "active-hermes").resolve(),
        isolated_hermes_root=output / "platform" / "hermes",
    )
    plan = harness.build_command_plan(
        admission,
        extracted=output / "source",
        install_source=output / "profile-install-source",
        wheel=output / "artifacts" / "non_profit_hermes-1.0.0-py3-none-any.whl",
        venv_python=output / "venv" / "Scripts" / "python.exe",
        console=output / "venv" / "Scripts" / "nonprofit-hermes.exe",
        external_cwd=output / "work",
    )
    assert plan["profile_install"] == (
        "hermes",
        "profile",
        "install",
        str(output / "profile-install-source"),
        "--name",
        "nonprofit-v1-test-001",
        "-y",
    )
    assert str(output / "source") not in plan["profile_install"]


def test_built_sdist_contains_only_portable_package_and_distribution_assets(tmp_path: Path) -> None:
    harness = load_harness()
    artifacts = tmp_path / "artifacts"
    result = subprocess.run(
        ["uv", "build", "--sdist", "--out-dir", str(artifacts), str(ROOT)],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    sdists = sorted(artifacts.glob("non_profit_hermes-1.0.0.tar.gz"))
    assert len(sdists) == 1
    # The same archive classifier used by acceptance must accept the finished sdist.
    assert harness.verify_sdist_artifact(sdists[0])["version"] == "1.0.0"
    with tarfile.open(sdists[0], "r:gz") as archive:
        members = {
            "/".join(member.name.split("/")[1:])
            for member in archive.getmembers()
            if member.isfile()
        }
    required = {
        "README.md",
        "pyproject.toml",
        "non_profit_hermes/__init__.py",
        "non_profit_hermes/resources/defaults.toml",
        "distribution.yaml",
        "SOUL.md",
        "config.yaml",
        "skills/non-profit-hermes/SKILL.md",
        "plugins/non-profit-hermes/plugin.yaml",
        "plugins/non-profit-hermes/__init__.py",
        "plugins/non-profit-hermes/commands.py",
    }
    assert required <= members
    assert not any(
        path.startswith(("tests/", "reports/", "docs/", "proof", "data/"))
        for path in members
    )


def test_result_json_is_deterministic_secret_free_and_restart_safe(tmp_path: Path) -> None:
    harness = load_harness()
    payload = {
        "schema_version": 1,
        "status": "passed",
        "source_sha": "c" * 40,
        "production_touched": False,
        "stages": [{"name": "archive", "status": "passed"}],
        "commands": [
            {
                "stage": "profile_install",
                "argv": ["hermes", "profile", "install", "<EXTRACTED>"],
            }
        ],
        "limitations": ["physical-device acceptance not performed"],
    }
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    harness.write_result_json(first, payload, forbidden_values=("synthetic-private",))
    harness.write_result_json(second, payload, forbidden_values=("synthetic-private",))

    assert first.read_bytes() == second.read_bytes()
    assert first.read_text(encoding="utf-8").endswith("\n")
    assert json.loads(first.read_text(encoding="utf-8"))["production_touched"] is False
    with pytest.raises(harness.HarnessError) as collision:
        harness.write_result_json(first, payload, forbidden_values=())
    assert collision.value.code == "RESULT_COLLISION"

    leaked = dict(payload)
    leaked["limitations"] = ["synthetic-private"]
    with pytest.raises(harness.HarnessError) as leak:
        harness.write_result_json(tmp_path / "leak.json", leaked, forbidden_values=("synthetic-private",))
    assert leak.value.code == "RESULT_SECRET_LEAK"
    assert not (tmp_path / "leak.json").exists()


def test_cli_help_documents_required_safe_contract_without_running_harness() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--source" in result.stdout
    assert "--output-root" in result.stdout
    assert "--profile" in result.stdout
    assert "--keep" in result.stdout
    assert "--json" in result.stdout
    assert "unique disposable directory" in result.stdout.lower()


def test_run_acceptance_executes_ordered_disposable_stages_and_writes_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    harness = load_harness()
    output = (tmp_path / "cache" / "run-001").resolve()
    output.parent.mkdir(parents=True)
    admission = harness.Admission(
        source=(tmp_path / "clean-source").resolve(),
        output_root=output,
        profile="nonprofit-v1-test-001",
        source_head="d" * 40,
        allowed_cache_root=output.parent,
        active_hermes_root=(tmp_path / "active-hermes").resolve(),
        isolated_hermes_root=output / "platform" / "hermes",
    )
    admission.source.mkdir()
    commands: list[tuple[str, ...]] = []
    doctor_payload = json.dumps(
        {
            "schema_version": 1,
            "mode": "offline",
            "profile": admission.profile,
            "strict": True,
            "package_version": "1.0.0",
            "summary": {"pass": 10, "warn": 0, "fail": 0, "skip": 5},
            "checks": [],
            "exit_code": 0,
        },
        sort_keys=True,
    )

    def fake_runner(argv, **kwargs):
        command = tuple(str(value) for value in argv)
        commands.append(command)
        # Robust detection for git archive (supports global options like -c before subcommand)
        if command and command[0] == "git" and "archive" in command:
            try:
                out_idx = command.index("--output")
                Path(command[out_idx + 1]).write_bytes(b"archive")
            except (ValueError, IndexError):
                pass
        elif command[:2] == ("uv", "build"):
            artifacts = output / "artifacts"
            (artifacts / "non_profit_hermes-1.0.0-py3-none-any.whl").write_bytes(b"wheel")
            (artifacts / "non_profit_hermes-1.0.0.tar.gz").write_bytes(b"sdist")
        elif "profile" in command and "install" in command:
            (admission.isolated_hermes_root / "profiles" / admission.profile).mkdir(
                parents=True
            )
        elif "non_profit_hermes.doctor" in command or any(
            "nonprofit-hermes" in value for value in command[:1]
        ):
            return harness.CommandResult(0, doctor_payload, "")
        elif "plugin" in command[-1] if command else False:
            return harness.CommandResult(0, json.dumps(list(EXPECTED_COMMANDS)), "")
        elif "pytest" in command:
            return harness.CommandResult(0, "350 passed, 69 subtests passed in 1.00s\n", "")
        return harness.CommandResult(0, "", "")

    def fake_extract(_archive: Path, destination: Path):
        destination.mkdir()
        (destination / "README.md").write_text("safe\n", encoding="utf-8")
        return ("README.md",)

    monkeypatch.setattr(harness, "safe_extract_archive", fake_extract)
    monkeypatch.setattr(harness, "scan_private_material", lambda root: {})
    monkeypatch.setattr(
        harness,
        "build_profile_install_source",
        lambda archive_path, destination: {
            "archive_sha256": "0" * 64,
            "file_count": 1,
            "git_metadata_absent": True,
            "required_assets_present": True,
        },
    )
    monkeypatch.setattr(
        harness,
        "verify_wheel_artifact",
        lambda wheel, source: {
            "console_entrypoint": True,
            "member_count": 10,
            "sha256": "1" * 64,
            "version": "1.0.0",
        },
    )
    monkeypatch.setattr(
        harness,
        "verify_sdist_artifact",
        lambda sdist: {"member_count": 20, "sha256": "2" * 64, "version": "1.0.0"},
    )
    monkeypatch.setattr(
        harness,
        "inspect_installed_profile",
        lambda profile_root, expected: {"profile_contract": True},
    )
    monkeypatch.setattr(
        harness,
        "stage_synthetic_configuration",
        lambda profile_root, output_root, environment: ("synthetic-secret",),
    )
    monkeypatch.setattr(harness, "snapshot_tree", lambda root: {"config.yaml": {"size": 1}})

    result = harness.run_acceptance(
        admission,
        inherited={"PATH": "host-path"},
        runner=fake_runner,
        build_tool="uv",
    )

    assert result["status"] == "passed"
    assert result["production_touched"] is False
    assert [stage["name"] for stage in result["stages"]] == [
        "archive",
        "archive_privacy",
        "archive_git_index",
        "profile_install_source",
        "build",
        "wheel_install",
        "profile_install",
        "profile_exclusions",
        "synthetic_configuration",
        "doctor_module",
        "doctor_console",
        "doctor_equivalence",
        "plugin_registration",
        "full_tests",
        "py_compile",
        "git_diff_check",
        "source_archive_parity",
    ]
    assert (output / "result.json").is_file()
    assert json.loads((output / "result.json").read_text(encoding="utf-8")) == result

    # Robust git archive detection (supports global options e.g. -c core.autocrlf=false before subcommand)
    def _git_has(cmd, sub):
        return bool(cmd and cmd[0] == "git" and sub in cmd)

    assert any(_git_has(command, "archive") for command in commands)
    # Additional coverage per 060B: plain git archive, -c form, unrelated git, ordered stages
    assert any(_git_has(command, "init") for command in commands)
    assert any(_git_has(command, "commit") for command in commands)
    assert any(_git_has(command, "diff") for command in commands)
    assert any(command[:2] == ("uv", "build") for command in commands)
    assert any(command[:3] == ("hermes", "profile", "install") for command in commands)


def test_main_derives_default_cache_boundary_and_runs_only_after_admission(
    tmp_path: Path,
    monkeypatch,
) -> None:
    harness = load_harness()
    local_app_data = tmp_path / "LocalAppData"
    platform_root = local_app_data / "hermes"
    existing_profiles = platform_root / "profiles"
    (existing_profiles / "builder-grok").mkdir(parents=True)
    source = tmp_path / "source"
    output = platform_root / "cache" / "run-001"
    admitted = harness.Admission(
        source=source.resolve(),
        output_root=output.resolve(),
        profile="nonprofit-v1-test-001",
        source_head="e" * 40,
        allowed_cache_root=(platform_root / "cache").resolve(),
        active_hermes_root=platform_root.resolve(),
        isolated_hermes_root=output.resolve() / "platform" / "hermes",
    )
    calls = []

    def fake_validate(**kwargs):
        calls.append(kwargs)
        return admitted

    monkeypatch.setattr(harness, "validate_admission", fake_validate)
    monkeypatch.setattr(
        harness,
        "run_acceptance",
        lambda admission, inherited, runner: {
            "schema_version": 1,
            "status": "passed",
            "source_sha": admission.source_head,
            "production_touched": False,
        },
    )
    stdout = StringIO()

    exit_code = harness.main(
        [
            "--source",
            str(source),
            "--output-root",
            str(output),
            "--profile",
            "nonprofit-v1-test-001",
            "--json",
        ],
        environ={"LOCALAPPDATA": str(local_app_data), "PATH": "host-path"},
        runner=lambda *args, **kwargs: None,
        stdout=stdout,
    )

    assert exit_code == 0
    assert json.loads(stdout.getvalue())["status"] == "passed"
    assert calls[0]["allowed_cache_root"] == platform_root / "cache"
    assert calls[0]["active_hermes_root"] == platform_root
    assert calls[0]["existing_profile_names"] == {"builder-grok"}


def test_failed_stage_stops_and_writes_secret_free_failure_evidence(tmp_path: Path) -> None:
    harness = load_harness()
    output = tmp_path / "cache" / "run-failed"
    output.parent.mkdir(parents=True)
    source = tmp_path / "source"
    source.mkdir()
    admission = harness.Admission(
        source=source.resolve(),
        output_root=output.resolve(),
        profile="nonprofit-v1-test-failed",
        source_head="f" * 40,
        allowed_cache_root=output.parent.resolve(),
        active_hermes_root=(tmp_path / "active").resolve(),
        isolated_hermes_root=output.resolve() / "platform" / "hermes",
    )

    def failing_runner(argv, **kwargs):
        return harness.CommandResult(9, "synthetic-private-output", "more-private-output")

    with pytest.raises(harness.HarnessError) as failure:
        harness.run_acceptance(
            admission,
            inherited={"PATH": "host-path"},
            runner=failing_runner,
            build_tool="uv",
        )

    assert failure.value.code == "ARCHIVE_FAILED"
    evidence = json.loads((output / "result.json").read_text(encoding="utf-8"))
    assert evidence["status"] == "failed"
    assert evidence["failure_code"] == "ARCHIVE_FAILED"
    assert evidence["production_touched"] is False
    assert evidence["stages"] == [
        {"name": "archive", "status": "failed", "code": "ARCHIVE_FAILED"}
    ]
    serialized = json.dumps(evidence)
    assert "synthetic-private-output" not in serialized
    assert "more-private-output" not in serialized
