"""Package-boundary, configuration, and legacy-wrapper tests for approved-safe sync."""
from __future__ import annotations

import ast
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_PATH = ROOT / "non_profit_hermes" / "approved_safe_sync.py"
LEGACY_PATH = ROOT / "scripts" / "sync_approved_safe_data.py"
EXPECTED_SYNC_NAMES = (
    "SyncConfigurationError",
    "creds",
    "sheets_service",
    "calendar_service",
    "read_sheet_rows",
    "esc",
    "html_list",
    "write_json",
    "write_page",
    "render_page",
    "write_both",
    "deduplicate_rows",
    "duplicate_count",
    "rejection_reason",
    "calendar_rejection_reason",
    "dry_run_metrics",
    "safe_needs_from_requests",
    "safe_donations",
    "safe_reports",
    "safe_volunteer_gaps",
    "safe_board_log",
    "safe_calendar_export",
    "build_pages",
    "collect_approved_safe_data",
    "write_public_site",
    "run_sync",
    "main",
)


def _load_legacy_wrapper():
    spec = importlib.util.spec_from_file_location("legacy_sync_approved_safe_data", LEGACY_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NoGoogleCalls:
    touched = False

    def __getattr__(self, _name):
        self.touched = True
        raise AssertionError("Google service was touched before configuration validation")


def _clear_runtime_configuration(monkeypatch, sync) -> None:
    for name in (
        "NON_PROFIT_HERMES_CREDENTIALS_FILE",
        "NON_PROFIT_HERMES_SPREADSHEET_ID",
        "NON_PROFIT_HERMES_CALENDAR_ID",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(sync, "TOKEN", None)
    monkeypatch.setattr(sync, "SPREADSHEET_ID", None)
    monkeypatch.setattr(sync, "CALENDAR_ID", None)


def test_package_owns_the_complete_sync_contract() -> None:
    from non_profit_hermes import approved_safe_sync

    assert set(EXPECTED_SYNC_NAMES) <= set(approved_safe_sync.__all__)
    assert all(
        getattr(approved_safe_sync, name).__module__ == approved_safe_sync.__name__
        for name in EXPECTED_SYNC_NAMES
    )


def test_package_source_is_portable_and_uses_canonical_boundaries() -> None:
    source = PACKAGE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    imported_modules.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )

    assert "from non_profit_hermes import config, models, oauth_refresh" in source
    assert "sys.path" not in source
    assert "C:\\Users\\" not in source
    assert "/Users/" not in source
    assert "non_profit_hermes_schema" not in imported_modules
    assert "google_oauth_refresh" not in imported_modules
    assert not any(module == "scripts" or module.startswith("scripts.") for module in imported_modules)
    assert "1Sf68PnxsuqW2PVzHZgyh8vV90Y4UlJ-GYexQ7JlOxlE" not in source
    assert "e1c99cc72c43a87bb340a6e867f0b56c" not in source
    assert "google_token.json" not in source


def test_missing_credentials_fail_redacted_before_file_or_network_access(monkeypatch) -> None:
    from non_profit_hermes import approved_safe_sync

    _clear_runtime_configuration(monkeypatch, approved_safe_sync)

    with pytest.raises(approved_safe_sync.SyncConfigurationError) as error:
        approved_safe_sync.creds()

    message = str(error.value)
    assert "NON_PROFIT_HERMES_CREDENTIALS_FILE" in message
    assert "fallo" not in message.lower()
    assert "token" not in message.lower()


def test_missing_spreadsheet_configuration_fails_before_service_access(monkeypatch) -> None:
    from non_profit_hermes import approved_safe_sync

    _clear_runtime_configuration(monkeypatch, approved_safe_sync)
    service = NoGoogleCalls()

    with pytest.raises(approved_safe_sync.SyncConfigurationError) as error:
        approved_safe_sync.read_sheet_rows(service, "Requests")

    assert "NON_PROFIT_HERMES_SPREADSHEET_ID" in str(error.value)
    assert service.touched is False


def test_missing_calendar_configuration_fails_before_service_access(monkeypatch) -> None:
    from non_profit_hermes import approved_safe_sync

    _clear_runtime_configuration(monkeypatch, approved_safe_sync)
    service = NoGoogleCalls()

    with pytest.raises(approved_safe_sync.SyncConfigurationError) as error:
        approved_safe_sync.safe_calendar_export([], service)

    assert "NON_PROFIT_HERMES_CALENDAR_ID" in str(error.value)
    assert service.touched is False


def test_legacy_wrapper_reexports_canonical_objects_by_identity() -> None:
    from non_profit_hermes import approved_safe_sync

    legacy = _load_legacy_wrapper()
    assert legacy.__all__ == approved_safe_sync.__all__
    assert all(
        getattr(legacy, name) is getattr(approved_safe_sync, name)
        for name in approved_safe_sync.__all__
    )


def test_legacy_wrapper_contains_only_package_delegation() -> None:
    source = LEGACY_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert not any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        for node in ast.walk(tree)
    )
    assert len(source.splitlines()) <= 20
    assert "non_profit_hermes.approved_safe_sync" in source
    assert "googleapiclient" not in source
    assert "spreadsheets().values()" not in source
    assert "events_resource.list" not in source
    assert "sys.path" not in source


def test_package_and_wrapper_import_offline_from_external_cwd(tmp_path: Path) -> None:
    credential = tmp_path / "must-not-be-read.json"
    code = f"""
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
        path, _mode, flags = args
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
from non_profit_hermes import approved_safe_sync
assert tuple(sys.path) == before_path
spec = importlib.util.spec_from_file_location("external_legacy_sync", {os.fspath(LEGACY_PATH)!r})
assert spec and spec.loader
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)
assert all(getattr(legacy, name) is getattr(approved_safe_sync, name) for name in approved_safe_sync.__all__)
print("offline-sync-import-ok")
"""
    environment = os.environ.copy()
    environment.update(
        {
            "NON_PROFIT_HERMES_CREDENTIALS_FILE": os.fspath(credential),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "PYTHONPATH": os.fspath(ROOT),
        }
    )

    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "offline-sync-import-ok"
    assert not credential.exists()
    assert tuple(tmp_path.iterdir()) == ()


def test_cli_help_from_external_cwd_is_safe_and_write_free(tmp_path: Path) -> None:
    environment = os.environ.copy()
    for name in tuple(environment):
        if name.startswith("NON_PROFIT_HERMES_"):
            environment.pop(name)
    environment["PYTHONPATH"] = os.fspath(ROOT)
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"

    completed = subprocess.run(
        [sys.executable, os.fspath(LEGACY_PATH), "--help"],
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "--dry-run" in completed.stdout
    assert "fallo" not in completed.stdout.lower()
    assert os.fspath(ROOT) not in completed.stdout
    assert tuple(tmp_path.iterdir()) == ()
