"""Offline tests for CLEANUP-004's explicit, non-live runtime-plugin installer."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install_runtime_plugins.py"


def make_fixture(tmp_path: Path) -> Path:
    plugin = tmp_path / "runtime_plugins" / "non-profit-hermes-demo"
    plugin.mkdir(parents=True)
    (plugin / "plugin.yaml").write_text("name: demo\n", encoding="utf-8")
    (plugin / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
    files = [{"path": p, "sha256": hashlib.sha256((plugin / p).read_bytes()).hexdigest()} for p in ("__init__.py", "plugin.yaml")]
    (tmp_path / "RUNTIME_PLUGIN_MANIFEST.json").write_text(json.dumps({"version": 1, "plugins": [{"name": "demo", "directory": "non-profit-hermes-demo", "files": files, "mutable_paths": ["state.json"]}]}), encoding="utf-8")
    return tmp_path


def run_installer(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(INSTALLER), "--repo-root", str(repo), *args], text=True, capture_output=True, check=False)


def test_default_is_dry_run_and_does_not_create_target(tmp_path: Path):
    repo = make_fixture(tmp_path)
    target = tmp_path / "target"
    result = run_installer(repo, "--target-root", str(target))
    assert result.returncode == 0, result.stderr
    assert "DRY-RUN" in result.stdout
    assert not target.exists()


def test_apply_requires_explicit_target_root(tmp_path: Path):
    repo = make_fixture(tmp_path)
    result = run_installer(repo, "--apply")
    assert result.returncode != 0
    assert "--target-root" in result.stderr


def test_apply_installs_atomically_backs_up_and_preserves_declared_mutable_state(tmp_path: Path):
    repo = make_fixture(tmp_path)
    target = tmp_path / "target"
    old = target / "non-profit-hermes-demo"
    old.mkdir(parents=True)
    (old / "__init__.py").write_text("VALUE = 0\n", encoding="utf-8")
    (old / "state.json").write_text("keep\n", encoding="utf-8")
    result = run_installer(repo, "--apply", "--target-root", str(target), "--allow-dirty-git")
    assert result.returncode == 0, result.stderr
    assert (old / "__init__.py").read_text(encoding="utf-8") == "VALUE = 1\n"
    assert (old / "state.json").read_text(encoding="utf-8") == "keep\n"
    assert list((target / ".cleanup_004_backups").rglob("__init__.py"))


def test_apply_rejects_live_root_without_live_flag(tmp_path: Path):
    repo = make_fixture(tmp_path)
    live = Path.home() / "AppData" / "Local" / "hermes" / "plugins"
    result = run_installer(repo, "--apply", "--target-root", str(live), "--allow-dirty-git")
    assert result.returncode != 0
    assert "--live" in result.stderr
