"""Safe offline parity: canonical tracked runtime source is byte-identical to installed source."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLED = Path.home() / "AppData" / "Local" / "hermes" / "plugins"


def test_canonical_source_and_metadata_match_installed_runtime_without_importing_plugins():
    manifest = json.loads((ROOT / "RUNTIME_PLUGIN_MANIFEST.json").read_text(encoding="utf-8"))
    assert [item["name"] for item in manifest["plugins"]] == ["daily", "event", "need", "donation", "report", "task", "inventory"]
    for plugin in manifest["plugins"]:
        canonical = ROOT / "runtime_plugins" / plugin["directory"]
        installed = INSTALLED / plugin["directory"]
        assert canonical.is_dir() and installed.is_dir()
        assert not list(canonical.rglob("__pycache__"))
        for entry in plugin["files"]:
            source = canonical / entry["path"]
            runtime = installed / entry["path"]
            assert source.read_bytes() == runtime.read_bytes(), f"{plugin['name']}/{entry['path']}"
            assert hashlib.sha256(source.read_bytes()).hexdigest() == entry["sha256"]
