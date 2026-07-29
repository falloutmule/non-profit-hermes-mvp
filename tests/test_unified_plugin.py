"""Canonical unified Non-Profit Hermes plugin contract tests."""
from __future__ import annotations

import ast
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from non_profit_hermes import router


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugins" / "non-profit-hermes"
PLUGIN_INIT = PLUGIN_ROOT / "__init__.py"
PLUGIN_COMMANDS = PLUGIN_ROOT / "commands.py"

EXPECTED_COMMANDS = (
    (
        "daily",
        "Non-Profit Hermes board-safe daily summary",
        "",
    ),
    (
        "need",
        "Non-Profit Hermes: create a safe board-visible need request through the router/backend.",
        "id=REQ-... description=... urgency=normal needed_by=unknown location=public-safe-test-area privacy_level=board-visible next_action=review",
    ),
    (
        "donation",
        "Non-Profit Hermes: create a safe donation draft through the router/backend.",
        "id=DON-... item=... quantity=... pickup_or_dropoff=... location=... available_date=... receipt_needed=... consent_to_public_thanks=... next_action=review",
    ),
    (
        "report",
        "Non-Profit Hermes: submit a report.",
        "type=... summary=...",
    ),
    (
        "task",
        "Non-Profit Hermes: create a task.",
        "title=... assigned_to=... due_date=...",
    ),
    (
        "inventory",
        "Non-Profit Hermes: track inventory.",
        "item=... quantity=... unit=...",
    ),
    (
        "event",
        "Non-Profit Hermes: draft-first /event — writes a Sheet-only EventDraft; exact locally authorized one-shot promotion is the only exception, with no permanent Calendar enablement.",
        'event_title="Safe test event" start=2099-01-01T09:00:00-06:00 end=2099-01-01T10:00:00-06:00 type=meeting location="safe venue"',
    ),
)


class FakeContext:
    def __init__(self) -> None:
        self.commands: list[dict[str, object]] = []

    def register_command(
        self,
        name: str,
        handler,
        description: str = "",
        args_hint: str = "",
    ) -> None:
        self.commands.append(
            {
                "name": name,
                "handler": handler,
                "description": description,
                "args_hint": args_hint,
            }
        )


def load_plugin(module_name: str):
    for loaded_name in tuple(sys.modules):
        if loaded_name == module_name or loaded_name.startswith(module_name + "."):
            sys.modules.pop(loaded_name)
    spec = importlib.util.spec_from_file_location(
        module_name,
        PLUGIN_INIT,
        submodule_search_locations=[str(PLUGIN_ROOT)],
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def parse_simple_manifest(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def test_manifest_is_exact_shareable_standalone_v1() -> None:
    assert parse_simple_manifest(PLUGIN_ROOT / "plugin.yaml") == {
        "name": "non-profit-hermes",
        "version": "1.0.0",
        "description": "Unified shareable command interface for Non-Profit Hermes operations.",
        "kind": "standalone",
    }


def test_registers_exact_metadata_in_order_and_is_context_idempotent(monkeypatch) -> None:
    boundary_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        router,
        "run_plugin_command",
        lambda name, raw_args: boundary_calls.append((name, raw_args)),
    )
    plugin = load_plugin("unified_plugin_registration_test")
    first = FakeContext()
    second = FakeContext()

    plugin.register(first)
    plugin.register(first)
    plugin.register(second)

    for context in (first, second):
        assert [
            (entry["name"], entry["description"], entry["args_hint"])
            for entry in context.commands
        ] == list(EXPECTED_COMMANDS)
        assert len({entry["name"] for entry in context.commands}) == 7
    assert boundary_calls == []


def test_handlers_delegate_directly_to_one_package_boundary(monkeypatch) -> None:
    plugin = load_plugin("unified_plugin_delegation_test")
    context = FakeContext()
    plugin.register(context)
    calls: list[tuple[str, str]] = []

    def fake_boundary(name: str, raw_args: str) -> str:
        calls.append((name, raw_args))
        return f"handled:{name}:{raw_args}"

    monkeypatch.setattr(router, "run_plugin_command", fake_boundary)
    for entry in context.commands:
        name = str(entry["name"])
        handler = entry["handler"]
        assert handler("offline args") == f"handled:{name}:offline args"

    assert calls == [(name, "offline args") for name, _description, _hint in EXPECTED_COMMANDS]


@pytest.mark.parametrize("name", [item[0] for item in EXPECTED_COMMANDS])
def test_handlers_return_command_specific_redacted_errors(monkeypatch, name: str) -> None:
    plugin = load_plugin(f"unified_plugin_error_test_{name}")
    context = FakeContext()
    plugin.register(context)
    handler = next(entry["handler"] for entry in context.commands if entry["name"] == name)
    private_error = "PRIVATE-SENTINEL C:/private/location credential-marker"

    def fail_boundary(_name: str, _raw_args: str) -> str:
        raise RuntimeError(private_error)

    monkeypatch.setattr(router, "run_plugin_command", fail_boundary)
    response = handler("anything")

    assert response == (
        f"Non-Profit Hermes could not run /{name}. "
        "Please try again or check gateway logs."
    )
    assert private_error not in response
    assert "Traceback" not in response
    assert "C:/" not in response


def test_plugin_sources_are_thin_and_forbid_runtime_integrations() -> None:
    init_source = PLUGIN_INIT.read_text(encoding="utf-8")
    commands_source = PLUGIN_COMMANDS.read_text(encoding="utf-8")
    combined = init_source + "\n" + commands_source
    forbidden_text = (
        "sys.path",
        "subprocess",
        "scripts.",
        "scripts/",
        "googleapiclient",
        "google.auth",
        "C:\\Users\\",
        "/Users/",
        "6080816249",
        "credentials_file",
        "TOKEN_PATH",
        "importlib.reload",
    )
    assert all(value not in combined for value in forbidden_text)
    assert "run_plugin_command" not in init_source
    assert commands_source.count("router.run_plugin_command") == 1

    imported_modules: set[str] = set()
    for source in (init_source, commands_source):
        tree = ast.parse(source)
        imported_modules.update(
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        )
        imported_modules.update(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
    assert not any(module == "scripts" or module.startswith("scripts.") for module in imported_modules)
    assert not any(module.startswith("google") for module in imported_modules)


def test_hermes_compatible_import_and_registration_work_from_external_cwd(tmp_path: Path) -> None:
    script = f"""
import importlib.util
import json
import sys
from pathlib import Path

plugin_root = Path({str(PLUGIN_ROOT)!r})
spec = importlib.util.spec_from_file_location(
    "external_unified_plugin",
    plugin_root / "__init__.py",
    submodule_search_locations=[str(plugin_root)],
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

class Context:
    def __init__(self):
        self.items = []
    def register_command(self, name, handler, description="", args_hint=""):
        self.items.append((name, description, args_hint))

context = Context()
module.register(context)
module.register(context)
print(json.dumps(context.items))
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        value for value in (str(ROOT), environment.get("PYTHONPATH", "")) if value
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [list(item) for item in EXPECTED_COMMANDS]
