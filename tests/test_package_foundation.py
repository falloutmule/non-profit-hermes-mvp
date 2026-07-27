from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tomllib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_legacy_schema():
    path = REPO_ROOT / "scripts" / "non_profit_hermes_schema.py"
    spec = importlib.util.spec_from_file_location("legacy_non_profit_hermes_schema", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_package_import_exposes_version_matching_project_metadata() -> None:
    import non_profit_hermes

    metadata = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert metadata["project"]["version"] == "1.0.0"
    assert non_profit_hermes.__version__ == metadata["project"]["version"]


def test_packaged_defaults_are_sanitized_shareable_constants() -> None:
    from non_profit_hermes.config import load_packaged_defaults

    defaults = load_packaged_defaults()

    assert defaults == {
        "version": "1.0.0",
        "public_marker": "CLEAN_DOCS_DEPLOY_NON_PROFIT_HERMES_002",
        "commands": ["daily", "need", "donation", "report", "task", "inventory", "event"],
    }
    assert load_packaged_defaults() == defaults


def test_config_defaults_are_home_based_and_do_not_select_credentials(tmp_path: Path) -> None:
    from non_profit_hermes.config import resolve_config

    home = tmp_path / "isolated-home"

    config = resolve_config(environ={}, home=home)

    assert config.config_dir == home / ".config" / "non-profit-hermes"
    assert config.data_dir == home / ".local" / "share" / "non-profit-hermes"
    assert config.state_dir == home / ".local" / "state" / "non-profit-hermes"
    assert config.public_dir == config.data_dir / "public"
    assert config.credentials_file is None
    assert config.spreadsheet_id is None
    assert config.calendar_id is None


def test_config_uses_documented_environment_over_home_defaults(
    tmp_path: Path, monkeypatch,
) -> None:
    from non_profit_hermes.config import resolve_config

    paths = {
        "NON_PROFIT_HERMES_CONFIG_DIR": tmp_path / "configured" / "config",
        "NON_PROFIT_HERMES_DATA_DIR": tmp_path / "configured" / "data",
        "NON_PROFIT_HERMES_STATE_DIR": tmp_path / "configured" / "state",
        "NON_PROFIT_HERMES_PUBLIC_DIR": tmp_path / "configured" / "public",
        "NON_PROFIT_HERMES_CREDENTIALS_FILE": tmp_path / "configured" / "credentials.json",
    }
    environ = {name: str(path) for name, path in paths.items()}
    environ.update(
        {
            "NON_PROFIT_HERMES_SPREADSHEET_ID": "test-sheet",
            "NON_PROFIT_HERMES_CALENDAR_ID": "test-calendar",
        }
    )
    monkeypatch.chdir(tmp_path)

    config = resolve_config(environ=environ, home=tmp_path / "other-home")

    assert config.config_dir == paths["NON_PROFIT_HERMES_CONFIG_DIR"]
    assert config.data_dir == paths["NON_PROFIT_HERMES_DATA_DIR"]
    assert config.state_dir == paths["NON_PROFIT_HERMES_STATE_DIR"]
    assert config.public_dir == paths["NON_PROFIT_HERMES_PUBLIC_DIR"]
    assert config.credentials_file == paths["NON_PROFIT_HERMES_CREDENTIALS_FILE"]
    assert config.spreadsheet_id == "test-sheet"
    assert config.calendar_id == "test-calendar"


def test_explicit_config_arguments_override_environment(tmp_path: Path) -> None:
    from non_profit_hermes.config import resolve_config

    environment = {
        "NON_PROFIT_HERMES_CONFIG_DIR": str(tmp_path / "environment-config"),
        "NON_PROFIT_HERMES_DATA_DIR": str(tmp_path / "environment-data"),
        "NON_PROFIT_HERMES_STATE_DIR": str(tmp_path / "environment-state"),
        "NON_PROFIT_HERMES_PUBLIC_DIR": str(tmp_path / "environment-public"),
        "NON_PROFIT_HERMES_CREDENTIALS_FILE": str(tmp_path / "environment-token.json"),
        "NON_PROFIT_HERMES_SPREADSHEET_ID": "environment-sheet",
        "NON_PROFIT_HERMES_CALENDAR_ID": "environment-calendar",
    }
    explicit = {
        "config_dir": tmp_path / "argument-config",
        "data_dir": tmp_path / "argument-data",
        "state_dir": tmp_path / "argument-state",
        "public_dir": tmp_path / "argument-public",
        "credentials_file": tmp_path / "argument-token.json",
    }

    config = resolve_config(
        environ=environment,
        home=tmp_path / "home",
        **explicit,
        spreadsheet_id="argument-sheet",
        calendar_id="argument-calendar",
    )

    assert config.config_dir == explicit["config_dir"]
    assert config.data_dir == explicit["data_dir"]
    assert config.state_dir == explicit["state_dir"]
    assert config.public_dir == explicit["public_dir"]
    assert config.credentials_file == explicit["credentials_file"]
    assert config.spreadsheet_id == "argument-sheet"
    assert config.calendar_id == "argument-calendar"


def test_model_constants_preserve_legacy_schema_values_and_order() -> None:
    from non_profit_hermes import models

    legacy = load_legacy_schema()
    names = (
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
        "TAB_ORDER",
    )

    for name in names:
        assert getattr(models, name) == getattr(legacy, name), name
    assert list(models.HEADERS) == list(legacy.HEADERS)
    assert list(models.PRIMARY_KEYS) == list(legacy.PRIMARY_KEYS)


def test_model_validation_helpers_preserve_legacy_behavior() -> None:
    from non_profit_hermes import models

    legacy = load_legacy_schema()
    for column_number in (1, 26, 27, 52, 53):
        assert models.col(column_number) == legacy.col(column_number)
    for tab in legacy.TAB_ORDER:
        assert models.get_header_range(tab) == legacy.get_header_range(tab)
        assert models.get_full_range(tab) == legacy.get_full_range(tab)
        assert models.get_primary_key(tab) == legacy.get_primary_key(tab)
    assert models.get_primary_key("Missing") == legacy.get_primary_key("Missing")
    for value in ("yes", " APPROVED ", "no", ""):
        assert models.is_affirmative(value) == legacy.is_affirmative(value)
    for value in ("public-safe", " BOARD-VISIBLE ", "private-review", ""):
        assert models.is_approved_privacy(value) == legacy.is_approved_privacy(value)
    for tab, value in (("Requests", "OPEN"), ("Reports", "draft"), ("Tasks", "ready")):
        assert models.is_public_status(tab, value) == legacy.is_public_status(tab, value)
    for value in ("cancelled", " NEEDS-INFO ", "ready", ""):
        assert models.is_terminal_status(value) == legacy.is_terminal_status(value)
    assert models.validate_schema_consistency() == legacy.validate_schema_consistency() == []


def test_packaging_declares_runtime_test_and_private_data_boundaries() -> None:
    metadata = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert metadata["build-system"]["build-backend"] == "setuptools.build_meta"
    assert metadata["project"]["requires-python"] == ">=3.11,<3.14"
    assert metadata["project"]["dependencies"] == [
        "google-auth>=2,<3",
        "google-api-python-client>=2,<3",
        "PyYAML>=6,<7",
    ]
    assert metadata["project"]["scripts"] == {
        "nonprofit-hermes": "non_profit_hermes.doctor:main"
    }
    assert metadata["project"]["optional-dependencies"]["test"] == ["pytest>=8,<10"]
    assert metadata["tool"]["setuptools"]["include-package-data"] is False
    assert metadata["tool"]["setuptools"]["package-data"] == {
        "non_profit_hermes": ["resources/defaults.toml"]
    }
    assert metadata["tool"]["setuptools"]["packages"]["find"]["include"] == [
        "non_profit_hermes*"
    ]
    excluded_data = metadata["tool"]["setuptools"]["exclude-package-data"]["*"]
    assert {"*.env", "*.json", "*.db", "*.sqlite*", "*.log", "*.pem", "*.key", "*.token"} <= set(
        excluded_data
    )


def test_package_sources_have_no_production_path_or_scripts_import() -> None:
    changed_sources = [
        REPO_ROOT / "pyproject.toml",
        *sorted((REPO_ROOT / "non_profit_hermes").glob("*.py")),
    ]

    for path in changed_sources:
        source = path.read_text(encoding="utf-8")
        assert "C:/Users/fallo" not in source, path
        assert "C:\\Users\\fallo" not in source, path
        assert "sys.path" not in source, path
        assert "from scripts" not in source, path
        assert "import scripts" not in source, path
        assert "load_dotenv" not in source, path


def test_import_is_offline_side_effect_free_from_isolated_cwd(tmp_path: Path) -> None:
    isolated_home = tmp_path / "home"
    credential = tmp_path / "must-not-be-read.json"
    script = r'''
import os
import pathlib
import sys

credential = pathlib.Path(os.environ["NON_PROFIT_HERMES_CREDENTIALS_FILE"]).resolve()
write_flags = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND

def audit(event, args):
    if event in {"socket.connect", "socket.bind", "socket.getaddrinfo"}:
        raise RuntimeError(f"network during import: {event}")
    if event == "open":
        path, mode, flags = args
        try:
            opened = pathlib.Path(path).resolve()
        except TypeError:
            return
        if opened == credential:
            raise RuntimeError("credential read during import")
        if isinstance(flags, int) and flags & write_flags:
            raise RuntimeError(f"filesystem write during import: {opened}")

sys.addaudithook(audit)
before_path = tuple(sys.path)
before_environment = dict(os.environ)

import non_profit_hermes
import non_profit_hermes.config
import non_profit_hermes.models

assert non_profit_hermes.__version__ == "1.0.0"
assert non_profit_hermes.config.load_packaged_defaults()["commands"] == [
    "daily", "need", "donation", "report", "task", "inventory", "event"
]
assert tuple(sys.path) == before_path
assert dict(os.environ) == before_environment
print("offline-import-ok")
'''
    environment = os.environ.copy()
    environment.update(
        {
            "HOME": str(isolated_home),
            "USERPROFILE": str(isolated_home),
            "NON_PROFIT_HERMES_CONFIG_DIR": str(tmp_path / "config"),
            "NON_PROFIT_HERMES_DATA_DIR": str(tmp_path / "data"),
            "NON_PROFIT_HERMES_STATE_DIR": str(tmp_path / "state"),
            "NON_PROFIT_HERMES_CREDENTIALS_FILE": str(credential),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": str(REPO_ROOT),
        }
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "offline-import-ok"
    assert not credential.exists()
    assert not (tmp_path / "config").exists()
    assert not (tmp_path / "data").exists()
    assert not (tmp_path / "state").exists()
