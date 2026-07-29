"""Contract tests for the seven legacy Non-Profit Hermes compatibility shims."""
from __future__ import annotations

import ast
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from non_profit_hermes import router


ROOT = Path(__file__).resolve().parents[1]
LEGACY_ROOT = ROOT / "runtime_plugins"

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
EXPECTED_BY_NAME = {
    name: (description, args_hint)
    for name, description, args_hint in EXPECTED_COMMANDS
}
LEGACY_ORDER = ("daily", "event", "need", "donation", "report", "task", "inventory")


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


def plugin_root(name: str) -> Path:
    return LEGACY_ROOT / f"non-profit-hermes-{name}"


def load_plugin(name: str, module_name: str):
    init_path = plugin_root(name) / "__init__.py"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, init_path)
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


def test_manifests_are_deprecated_v1_compatibility_plugins() -> None:
    for name in LEGACY_ORDER:
        manifest = parse_simple_manifest(plugin_root(name) / "plugin.yaml")
        assert manifest.keys() == {"name", "version", "description", "author", "kind"}
        assert manifest["name"] == f"non-profit-hermes-{name}"
        assert manifest["version"] == "1.0.0"
        assert manifest["author"] == "Hermes Agent"
        assert manifest["kind"] == "standalone"
        description = manifest["description"].lower()
        assert "compatibility" in description
        assert "deprecated" in description


def test_each_shim_registers_only_its_historical_command_without_boundary_calls(monkeypatch) -> None:
    boundary_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        router,
        "run_plugin_command",
        lambda name, args: boundary_calls.append((name, args)),
    )

    for name in LEGACY_ORDER:
        plugin = load_plugin(name, f"legacy_registration_{name}")
        context = FakeContext()
        plugin.register(context)
        description, args_hint = EXPECTED_BY_NAME[name]
        assert [
            (entry["name"], entry["description"], entry["args_hint"])
            for entry in context.commands
        ] == [(name, description, args_hint)]

    assert boundary_calls == []


@pytest.mark.parametrize("name", LEGACY_ORDER)
def test_each_shim_delegates_directly_to_the_package_boundary(monkeypatch, name: str) -> None:
    calls: list[tuple[str, str]] = []

    def fake_boundary(command_name: str, raw_args: str) -> str:
        calls.append((command_name, raw_args))
        return f"offline:{command_name}:{raw_args}"

    monkeypatch.setattr(router, "run_plugin_command", fake_boundary)
    plugin = load_plugin(name, f"legacy_delegation_{name}")
    context = FakeContext()
    plugin.register(context)

    assert context.commands[0]["handler"]("offline args") == f"offline:{name}:offline args"
    assert calls == [(name, "offline args")]


@pytest.mark.parametrize("name", LEGACY_ORDER)
def test_each_shim_returns_a_command_specific_redacted_error(monkeypatch, name: str) -> None:
    private_error = "PRIVATE-SENTINEL C:/private/location credential-marker"

    def fail_boundary(_command_name: str, _raw_args: str) -> str:
        raise RuntimeError(private_error)

    monkeypatch.setattr(router, "run_plugin_command", fail_boundary)
    plugin = load_plugin(name, f"legacy_error_{name}")
    context = FakeContext()
    plugin.register(context)
    response = context.commands[0]["handler"]("anything")

    assert response == (
        f"Non-Profit Hermes could not run /{name}. "
        "Please try again or check gateway logs."
    )
    assert private_error not in response
    assert "Traceback" not in response
    assert "C:/" not in response


def test_shims_are_thin_and_obsolete_duplicate_entrypoints_are_absent() -> None:
    forbidden_text = (
        "sys.path",
        "subprocess",
        "scripts.",
        "scripts/",
        "googleapiclient",
        "google.auth",
        "c:\\users\\",
        "/users/",
        "credentials_file",
        "token_path",
        "importlib.reload",
        "traceback",
        "state_dir",
        "state_path",
    )

    for name in LEGACY_ORDER:
        root = plugin_root(name)
        source = (root / "__init__.py").read_text(encoding="utf-8")
        manifest_source = (root / "plugin.yaml").read_text(encoding="utf-8")
        combined = (source + "\n" + manifest_source).lower()
        assert all(value not in combined for value in forbidden_text), name
        assert re.search(r"(?<![A-Za-z0-9-])\d{9,12}(?![A-Za-z0-9-])", combined) is None
        assert not (root / "init.py").exists()
        assert source.count("router.run_plugin_command") == 1

        tree = ast.parse(source)
        function_names = {
            node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        assert function_names == {f"_{name}", "register"}
        assert not any(isinstance(node, ast.ClassDef) for node in ast.walk(tree))

        imported_modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported_modules.add(node.module or "")
            elif isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
        assert imported_modules <= {"__future__", "non_profit_hermes"}


def test_external_cwd_import_registration_and_delegation_are_offline(tmp_path: Path) -> None:
    plugin_paths = {
        name: str(plugin_root(name) / "__init__.py")
        for name in LEGACY_ORDER
    }
    script = f"""
import importlib.util
import json
import sys
from non_profit_hermes import router

paths = {plugin_paths!r}
router.run_plugin_command = lambda name, args: f"offline:{{name}}:{{args}}"
items = []
class Context:
    def __init__(self):
        self.commands = []
    def register_command(self, name, handler, description="", args_hint=""):
        self.commands.append((name, handler, description, args_hint))

for name, path in paths.items():
    module_name = f"external_legacy_{{name}}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    context = Context()
    module.register(context)
    command, handler, description, args_hint = context.commands[0]
    items.append((command, description, args_hint, handler("external args")))
print(json.dumps(items))
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
    assert json.loads(result.stdout) == [
        [name, *EXPECTED_BY_NAME[name], f"offline:{name}:external args"]
        for name in LEGACY_ORDER
    ]
