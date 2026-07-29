"""Package-boundary, configuration, and legacy-wrapper tests for operations."""
from __future__ import annotations

import ast
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_PATH = ROOT / "non_profit_hermes" / "operations.py"
LEGACY_PATH = ROOT / "scripts" / "non_profit_hermes_ops.py"
EXPECTED_OPERATION_NAMES = (
    "now_utc",
    "ts",
    "gen_id",
    "get_creds",
    "sheets",
    "calendar",
    "append_row",
    "make_row",
    "ensure_header",
    "write_audit_log",
    "add_request",
    "update_request",
    "add_donation",
    "update_donation",
    "add_report",
    "update_report",
    "add_task",
    "update_task",
    "update_inventory",
    "create_calendar_event",
    "upsert_event_draft",
    "update_event_draft",
    "create_calendar_event_from_draft",
    "run_test_write",
    "main",
)


def _load_legacy_wrapper():
    spec = importlib.util.spec_from_file_location("legacy_non_profit_hermes_ops", LEGACY_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NoGoogleCalls:
    touched = False

    def __getattr__(self, _name):
        self.touched = True
        raise AssertionError("Google service was touched before configuration validation")


def _clear_runtime_configuration(monkeypatch, operations) -> None:
    for name in (
        "NON_PROFIT_HERMES_CREDENTIALS_FILE",
        "NON_PROFIT_HERMES_SPREADSHEET_ID",
        "NON_PROFIT_HERMES_CALENDAR_ID",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(operations, "TOKEN", None)
    monkeypatch.setattr(operations, "SPREADSHEET_ID", None)
    monkeypatch.setattr(operations, "CALENDAR_ID", None)


def test_package_owns_the_complete_operation_contract() -> None:
    from non_profit_hermes import operations

    assert set(EXPECTED_OPERATION_NAMES) <= set(operations.__all__)
    assert all(getattr(operations, name).__module__ == operations.__name__ for name in EXPECTED_OPERATION_NAMES)


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


def test_missing_spreadsheet_configuration_fails_before_service_access(monkeypatch) -> None:
    from non_profit_hermes import operations

    _clear_runtime_configuration(monkeypatch, operations)
    service = NoGoogleCalls()

    with pytest.raises(operations.OperationsConfigurationError) as error:
        operations.append_row(service, "AuditLog", [""] * len(operations.HEADERS["AuditLog"]))

    assert "NON_PROFIT_HERMES_SPREADSHEET_ID" in str(error.value)
    assert service.touched is False


def test_missing_calendar_configuration_fails_before_any_service_access(monkeypatch) -> None:
    from non_profit_hermes import operations

    _clear_runtime_configuration(monkeypatch, operations)
    monkeypatch.setattr(operations, "SPREADSHEET_ID", "synthetic-sheet")
    calendar = NoGoogleCalls()
    sheets = NoGoogleCalls()

    with pytest.raises(operations.OperationsConfigurationError) as error:
        operations.create_calendar_event(calendar, sheets, event_title="offline")

    assert "NON_PROFIT_HERMES_CALENDAR_ID" in str(error.value)
    assert calendar.touched is False
    assert sheets.touched is False


def test_missing_credentials_fail_redacted_before_file_or_network_access(monkeypatch) -> None:
    from non_profit_hermes import operations

    _clear_runtime_configuration(monkeypatch, operations)

    with pytest.raises(operations.OperationsConfigurationError) as error:
        operations.get_creds()

    message = str(error.value)
    assert "NON_PROFIT_HERMES_CREDENTIALS_FILE" in message
    assert "fallo" not in message.lower()
    assert "token" not in message.lower()


def test_environment_spreadsheet_configuration_is_resolved_at_call_time(monkeypatch) -> None:
    from non_profit_hermes import operations

    monkeypatch.setattr(operations, "SPREADSHEET_ID", None)
    monkeypatch.setenv("NON_PROFIT_HERMES_SPREADSHEET_ID", "synthetic-sheet")
    calls = []

    class Values:
        def append(self, **kwargs):
            calls.append(kwargs)
            return self

        def execute(self):
            return {"updates": {"updatedRows": 1}}

    class Service:
        def spreadsheets(self):
            return self

        def values(self):
            return Values()

    operations.append_row(Service(), "AuditLog", [""] * len(operations.HEADERS["AuditLog"]))

    assert calls[0]["spreadsheetId"] == "synthetic-sheet"


def test_legacy_wrapper_reexports_canonical_objects_by_identity() -> None:
    from non_profit_hermes import operations

    legacy = _load_legacy_wrapper()
    assert legacy.__all__ == operations.__all__
    assert all(getattr(legacy, name) is getattr(operations, name) for name in operations.__all__)


def test_legacy_wrapper_contains_only_package_delegation() -> None:
    source = LEGACY_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) for node in ast.walk(tree))
    assert len(source.splitlines()) <= 20
    assert "non_profit_hermes.operations" in source
    assert "googleapiclient" not in source
    assert "spreadsheets().values()" not in source
    assert "events().insert" not in source
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
from non_profit_hermes import operations
assert tuple(sys.path) == before_path
spec = importlib.util.spec_from_file_location("external_legacy_ops", {os.fspath(LEGACY_PATH)!r})
assert spec and spec.loader
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)
assert all(getattr(legacy, name) is getattr(operations, name) for name in operations.__all__)
print("offline-operations-import-ok")
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
    assert completed.stdout.strip() == "offline-operations-import-ok"
    assert not credential.exists()


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
    assert "--test-write" in completed.stdout
    assert "fallo" not in completed.stdout.lower()
    assert os.fspath(ROOT) not in completed.stdout
    assert tuple(tmp_path.iterdir()) == ()
