"""Deterministic offline parity for tracked unified and legacy plugin sources."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

from non_profit_hermes import router


ROOT = Path(__file__).resolve().parents[1]
LEGACY_ROOT = ROOT / "runtime_plugins"
UNIFIED_ROOT = ROOT / "plugins" / "non-profit-hermes"
CHECKER = ROOT / "scripts" / "check_runtime_plugin_drift.py"
LEGACY_ORDER = ("daily", "event", "need", "donation", "report", "task", "inventory")
UNIFIED_COMMANDS = ("daily", "need", "donation", "report", "task", "inventory", "event")


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


def load_plugin(module_name: str, root: Path):
    for loaded_name in tuple(sys.modules):
        if loaded_name == module_name or loaded_name.startswith(module_name + "."):
            sys.modules.pop(loaded_name)
    spec = importlib.util.spec_from_file_location(
        module_name,
        root / "__init__.py",
        submodule_search_locations=[str(root)],
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def index_source_bytes(source: Path) -> bytes:
    relative = source.relative_to(ROOT).as_posix()
    return subprocess.check_output(["git", "-C", str(ROOT), "show", f":{relative}"])


def test_unified_and_legacy_metadata_and_delegated_outputs_match_offline(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_boundary(name: str, raw_args: str) -> str:
        calls.append((name, raw_args))
        return f"offline:{name}:{raw_args}"

    monkeypatch.setattr(router, "run_plugin_command", fake_boundary)
    unified = load_plugin("offline_unified_parity", UNIFIED_ROOT)
    unified_context = FakeContext()
    unified.register(unified_context)
    unified_by_name = {
        str(entry["name"]): entry
        for entry in unified_context.commands
    }

    for name in LEGACY_ORDER:
        legacy = load_plugin(
            f"offline_legacy_parity_{name}",
            LEGACY_ROOT / f"non-profit-hermes-{name}",
        )
        legacy_context = FakeContext()
        legacy.register(legacy_context)
        assert len(legacy_context.commands) == 1
        legacy_entry = legacy_context.commands[0]
        unified_entry = unified_by_name[name]
        assert (
            legacy_entry["name"],
            legacy_entry["description"],
            legacy_entry["args_hint"],
        ) == (
            unified_entry["name"],
            unified_entry["description"],
            unified_entry["args_hint"],
        )
        assert legacy_entry["handler"]("parity args") == unified_entry["handler"]("parity args")

    expected_calls = [
        call
        for name in LEGACY_ORDER
        for call in ((name, "parity args"), (name, "parity args"))
    ]
    assert calls == expected_calls


def test_manifest_v2_is_unified_first_and_matches_exact_git_index_sources() -> None:
    manifest = json.loads((ROOT / "RUNTIME_PLUGIN_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "Non-Profit Hermes runtime plugin manifest"
    assert manifest["version"] == 2
    assert manifest["default_mode"] == "unified"

    unified, *legacy = manifest["plugins"]
    assert {
        key: unified[key]
        for key in ("name", "source", "directory", "role", "version", "commands")
    } == {
        "name": "non-profit-hermes",
        "source": "plugins/non-profit-hermes",
        "directory": "non-profit-hermes",
        "role": "primary",
        "version": "1.0.0",
        "commands": list(UNIFIED_COMMANDS),
    }
    assert [entry["path"] for entry in unified["files"]] == [
        "__init__.py",
        "commands.py",
        "plugin.yaml",
    ]
    assert [item["commands"][0] for item in legacy] == list(LEGACY_ORDER)
    assert [item["name"] for item in legacy] == [
        f"non-profit-hermes-{name}" for name in LEGACY_ORDER
    ]

    for plugin in manifest["plugins"]:
        source_path = Path(plugin["source"])
        assert not source_path.is_absolute()
        assert source_path.as_posix() == plugin["source"]
        assert ".." not in source_path.parts
        canonical = ROOT / source_path
        assert canonical.is_dir()
        manifest_values = dict(
            line.split(":", 1)
            for line in (canonical / "plugin.yaml").read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#")
        )
        assert manifest_values["name"].strip() == plugin["name"]
        assert manifest_values["version"].strip() == plugin["version"]
        if plugin["role"] == "compatibility":
            assert plugin["source"] == f"runtime_plugins/{plugin['directory']}"
            assert [entry["path"] for entry in plugin["files"]] == ["__init__.py", "plugin.yaml"]
            assert len(plugin["commands"]) == 1
        for entry in plugin["files"]:
            source = canonical / entry["path"]
            tracked = index_source_bytes(source)
            checkout = source.read_bytes()
            assert checkout == tracked or (
                b"\x0d" not in tracked
                and checkout == tracked.replace(b"\x0a", b"\x0d\x0a")
            ), f"{plugin['name']}/{entry['path']} has substantive checkout drift"
            assert hashlib.sha256(tracked).hexdigest() == entry["sha256"]


def test_strict_checker_rejects_synthetic_plugin_drift(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    canonical = repo / "runtime_plugins" / "non-profit-hermes-demo"
    installed = tmp_path / "installed" / "non-profit-hermes-demo"
    canonical.mkdir(parents=True)
    installed.mkdir(parents=True)
    files = {
        "__init__.py": b"VALUE = 1\n",
        "plugin.yaml": b"name: non-profit-hermes-demo\n",
    }
    for path, content in files.items():
        (canonical / path).write_bytes(content)
        (installed / path).write_bytes(content)
    manifest = {
        "version": 1,
        "plugins": [
            {
                "name": "demo",
                "directory": "non-profit-hermes-demo",
                "files": [
                    {"path": path, "sha256": hashlib.sha256(content).hexdigest()}
                    for path, content in files.items()
                ],
                "mutable_paths": ["__pycache__/**"],
            }
        ],
    }
    (repo / "RUNTIME_PLUGIN_MANIFEST.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )
    candidate = installed / "__init__.py"
    candidate.write_bytes(candidate.read_bytes() + b"# substantive drift\n")

    result = subprocess.run(
        [
            sys.executable,
            str(CHECKER),
            "--repo-root",
            str(repo),
            "--installed-root",
            str(installed.parent),
            "--strict",
        ],
        capture_output=True,
        check=False,
        env=os.environ.copy(),
        text=True,
    )

    assert result.returncode == 1
    assert "demo: UNEXPLAINED DRIFT" in result.stdout
    assert "canonical manifest mismatch" not in result.stdout
