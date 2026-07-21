from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_MODULES = (
    "config",
    "models",
    "oauth_refresh",
    "operations",
    "approved_safe_sync",
    "router",
)
LEGACY_WRAPPERS = {
    "legacy_google_oauth_refresh": ("google_oauth_refresh.py", "oauth_refresh"),
    "legacy_non_profit_hermes_ops": ("non_profit_hermes_ops.py", "operations"),
    "legacy_sync_approved_safe_data": ("sync_approved_safe_data.py", "approved_safe_sync"),
    "legacy_telegram_intake_router": ("telegram_intake_router.py", "router"),
}
SCHEMA_PUBLIC_NAMES = (
    "HEADERS",
    "PRIMARY_KEYS",
    "AFFIRMATIVE_VALUES",
    "APPROVED_PRIVACY_LEVELS",
    "TERMINAL_STATUSES",
    "PUBLIC_STATUS_BY_TYPE",
    "PUBLIC_SUMMARY_ALLOWED_FIELD",
    "PUBLIC_LISTING_ALLOWED_FIELD",
    "PRIVACY_LEVEL_FIELD",
    "LAST_UPDATED_FIELD",
    "CONSENT_TO_SHARE_FIELD",
    "CONSENT_TO_PUBLIC_THANKS_FIELD",
    "col",
    "get_header_range",
    "get_full_range",
    "get_primary_key",
    "is_affirmative",
    "is_approved_privacy",
    "is_public_status",
    "is_terminal_status",
    "validate_schema_consistency",
    "TAB_ORDER",
)


def build_wheel(wheelhouse: Path) -> Path:
    wheelhouse.mkdir(parents=True)
    source = wheelhouse.parent / "source"
    source.mkdir()
    shutil.copy2(REPO_ROOT / "pyproject.toml", source / "pyproject.toml")
    shutil.copy2(REPO_ROOT / "README.md", source / "README.md")
    shutil.copytree(REPO_ROOT / "non_profit_hermes", source / "non_profit_hermes")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            os.fspath(wheelhouse),
            os.fspath(source),
        ],
        cwd=wheelhouse,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    wheels = list(wheelhouse.glob("non_profit_hermes-1.0.0-*.whl"))
    assert len(wheels) == 1
    return wheels[0]


def test_wheel_contains_only_package_modules_metadata_and_sanitized_defaults(
    tmp_path: Path,
) -> None:
    wheel = build_wheel(tmp_path / "wheelhouse")

    with zipfile.ZipFile(wheel) as archive:
        members = set(archive.namelist())
        defaults_text = archive.read(
            "non_profit_hermes/resources/defaults.toml"
        ).decode("utf-8")
        entry_points_text = archive.read(
            "non_profit_hermes-1.0.0.dist-info/entry_points.txt"
        ).decode("utf-8")

    expected_package_members = {
        f"non_profit_hermes/{path.name}"
        for path in (REPO_ROOT / "non_profit_hermes").glob("*.py")
    } | {"non_profit_hermes/resources/defaults.toml"}
    package_members = {
        member for member in members if member.startswith("non_profit_hermes/")
    }
    metadata_members = members - package_members

    assert package_members == expected_package_members
    assert metadata_members
    assert all(".dist-info/" in member for member in metadata_members)
    assert all(
        Path(member).name
        in {"METADATA", "WHEEL", "entry_points.txt", "top_level.txt", "RECORD"}
        for member in metadata_members
    )
    assert entry_points_text == (
        "[console_scripts]\n"
        "nonprofit-hermes = non_profit_hermes.doctor:main\n"
    )
    assert defaults_text == (
        'version = "1.0.0"\n'
        'public_marker = "CLEAN_DOCS_DEPLOY_NON_PROFIT_HERMES_002"\n'
        'commands = ["daily", "need", "donation", "report", "task", "inventory", "event"]\n'
    )


def test_built_wheel_and_legacy_wrappers_import_offline_from_external_cwd(
    tmp_path: Path,
) -> None:
    wheel = build_wheel(tmp_path / "wheelhouse")
    external_cwd = tmp_path / "external-cwd"
    external_cwd.mkdir()
    credential = tmp_path / "must-not-be-read.json"
    code = f'''
import importlib
import importlib.util
import os
import pathlib
import sys

credential = pathlib.Path(os.environ["NON_PROFIT_HERMES_CREDENTIALS_FILE"]).resolve()
write_flags = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND

def audit(event, args):
    if event in {{"socket.connect", "socket.bind", "socket.getaddrinfo"}}:
        raise RuntimeError(f"network during import: {{event}}")
    if event == "open":
        path, mode, flags = args
        try:
            opened = pathlib.Path(path).resolve()
        except TypeError:
            return
        if opened == credential:
            raise RuntimeError("credential read during import")
        if isinstance(flags, int) and flags & write_flags:
            raise RuntimeError(f"filesystem write during import: {{opened}}")

sys.addaudithook(audit)
before_path = tuple(sys.path)

import non_profit_hermes
from non_profit_hermes import config, models
assert non_profit_hermes.__version__ == "1.0.0"
assert config.load_packaged_defaults() == {{
    "version": "1.0.0",
    "public_marker": "CLEAN_DOCS_DEPLOY_NON_PROFIT_HERMES_002",
    "commands": ["daily", "need", "donation", "report", "task", "inventory", "event"],
}}
for module_name in {PACKAGE_MODULES!r}:
    importlib.import_module(f"non_profit_hermes.{{module_name}}")

schema_path = pathlib.Path({os.fspath(REPO_ROOT / "scripts" / "non_profit_hermes_schema.py")!r})
spec = importlib.util.spec_from_file_location("external_legacy_schema", schema_path)
assert spec and spec.loader
legacy_schema = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy_schema)
assert legacy_schema.__all__ == list({SCHEMA_PUBLIC_NAMES!r})
for name in legacy_schema.__all__:
    assert getattr(legacy_schema, name) is getattr(models, name), name

wrapper_specs = {LEGACY_WRAPPERS!r}
for legacy_name, (filename, canonical_name) in wrapper_specs.items():
    path = pathlib.Path({os.fspath(REPO_ROOT / "scripts")!r}) / filename
    spec = importlib.util.spec_from_file_location(legacy_name, path)
    assert spec and spec.loader
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)
    canonical = importlib.import_module(f"non_profit_hermes.{{canonical_name}}")
    assert legacy.__all__ == canonical.__all__
    for name in legacy.__all__:
        assert getattr(legacy, name) is getattr(canonical, name), (filename, name)

assert tuple(sys.path) == before_path
print("external-wheel-import-ok")
'''
    environment = os.environ.copy()
    environment.update(
        {
            "HOME": os.fspath(tmp_path / "home"),
            "USERPROFILE": os.fspath(tmp_path / "home"),
            "NON_PROFIT_HERMES_CREDENTIALS_FILE": os.fspath(credential),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "PYTHONPATH": os.fspath(wheel),
        }
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=external_cwd,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "external-wheel-import-ok"
    assert not credential.exists()


def test_portable_sources_have_no_user_path_or_sys_path_mutation() -> None:
    paths = [
        *sorted((REPO_ROOT / "non_profit_hermes").glob("*.py")),
        *(REPO_ROOT / "scripts" / filename for filename, _ in LEGACY_WRAPPERS.values()),
        REPO_ROOT / "scripts" / "non_profit_hermes_schema.py",
        REPO_ROOT / "non_profit_hermes" / "resources" / "defaults.toml",
    ]

    for path in paths:
        source = path.read_text(encoding="utf-8")
        assert "C:/Users/" not in source, path
        assert "C:\\Users\\" not in source, path
        assert "sys.path" not in source, path
