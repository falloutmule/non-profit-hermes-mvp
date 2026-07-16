"""Safe offline parity: canonical tracked runtime source is byte-identical to installed source."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLED = Path.home() / "AppData" / "Local" / "hermes" / "plugins"
CHECKER = ROOT / "scripts" / "check_runtime_plugin_drift.py"


def tracked_source_bytes(source: Path) -> bytes:
    relative = source.relative_to(ROOT).as_posix()
    return subprocess.check_output(["git", "-C", str(ROOT), "show", f"HEAD:{relative}"])


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
            tracked = tracked_source_bytes(source)
            checkout = source.read_bytes()
            assert checkout == tracked or (
                b"\x0d" not in tracked and checkout == tracked.replace(b"\x0a", b"\x0d\x0a")
            ), f"{plugin['name']}/{entry['path']} has substantive checkout drift"
            assert runtime.read_bytes() == tracked, f"{plugin['name']}/{entry['path']}"
            assert hashlib.sha256(tracked).hexdigest() == entry["sha256"]


def test_strict_checker_rejects_substantive_installed_plugin_drift_after_checkout_eol_conversion(tmp_path: Path):
    installed = tmp_path / "plugins"
    shutil.copytree(INSTALLED, installed)
    candidate = installed / "non-profit-hermes-daily" / "__init__.py"
    candidate.write_bytes(candidate.read_bytes() + b"# substantive drift\n")

    result = subprocess.run(
        [sys.executable, str(CHECKER), "--repo-root", str(ROOT), "--installed-root", str(installed), "--strict"],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 1
    assert "daily: UNEXPLAINED DRIFT" in result.stdout
    assert "canonical manifest mismatch" not in result.stdout
