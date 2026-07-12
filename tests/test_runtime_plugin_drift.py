"""Offline tests for CLEANUP-004's read-only runtime-plugin drift checker."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "check_runtime_plugin_drift.py"


def make_fixture(tmp_path: Path) -> tuple[Path, Path]:
    canonical = tmp_path / "runtime_plugins"
    installed = tmp_path / "installed"
    plugin = canonical / "non-profit-hermes-demo"
    plugin.mkdir(parents=True)
    (plugin / "plugin.yaml").write_text("name: demo\n", encoding="utf-8")
    (plugin / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
    manifest = {
        "version": 1,
        "plugins": [{"name": "demo", "directory": "non-profit-hermes-demo", "files": [
            {"path": "__init__.py", "sha256": "b6c11985b7720c15580c1b1dac6a53b12254777518f0d8ea5b6892c8e768e90e"},
            {"path": "plugin.yaml", "sha256": "cb2d32547da87ed7b8b831d616a75f2be75eef2aee08bbb6bf9aecdf08d7f20a"},
        ], "mutable_paths": ["__pycache__/**"]}],
    }
    # hashes are corrected by the production tool in the test setup itself.
    import hashlib
    for item in manifest["plugins"][0]["files"]:
        item["sha256"] = hashlib.sha256((plugin / item["path"]).read_bytes()).hexdigest()
    (tmp_path / "RUNTIME_PLUGIN_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    target = installed / "non-profit-hermes-demo"
    target.mkdir(parents=True)
    for path in ("__init__.py", "plugin.yaml"):
        (target / path).write_bytes((plugin / path).read_bytes())
    return tmp_path, installed


def run_checker(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(CHECKER), "--repo-root", str(repo), *args], text=True, capture_output=True, check=False)


def test_json_reports_match_and_expected_bytecode_derivation(tmp_path: Path):
    repo, installed = make_fixture(tmp_path)
    cache = installed / "non-profit-hermes-demo" / "__pycache__"
    cache.mkdir()
    (cache / "x.pyc").write_bytes(b"derived")
    result = run_checker(repo, "--installed-root", str(installed), "--json")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["plugins"][0]["classification"] == "EXPECTED DERIVATION"
    assert data["plugins"][0]["details"]["expected_derivations"] == ["__pycache__/x.pyc"]


def test_strict_fails_for_unexplained_drift_but_checker_never_writes(tmp_path: Path):
    repo, installed = make_fixture(tmp_path)
    candidate = installed / "non-profit-hermes-demo" / "__init__.py"
    before = candidate.stat().st_mtime_ns
    candidate.write_text("VALUE = 2\n", encoding="utf-8")
    result = run_checker(repo, "--installed-root", str(installed), "--strict")
    assert result.returncode == 1
    assert "UNEXPLAINED DRIFT" in result.stdout
    assert candidate.stat().st_mtime_ns >= before


def test_explained_mutable_state_and_untested_are_classified(tmp_path: Path):
    repo, installed = make_fixture(tmp_path)
    manifest_path = repo / "RUNTIME_PLUGIN_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["plugins"][0]["mutable_paths"] = ["state.json"]
    (installed / "non-profit-hermes-demo" / "state.json").write_text("local\n", encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    result = run_checker(repo, "--installed-root", str(installed), "--json")
    assert json.loads(result.stdout)["plugins"][0]["classification"] == "EXPLAINED MUTABLE STATE"
    (installed / "non-profit-hermes-demo" / "state.json").unlink()
    manifest["plugins"][0]["test_status"] = "untested"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    result = run_checker(repo, "--installed-root", str(installed), "--json")
    assert json.loads(result.stdout)["plugins"][0]["classification"] == "UNTESTED"


def test_missing_plugin_is_reported(tmp_path: Path):
    repo, installed = make_fixture(tmp_path)
    for item in installed.rglob("*"):
        if item.is_file(): item.unlink()
    (installed / "non-profit-hermes-demo").rmdir()
    result = run_checker(repo, "--installed-root", str(installed), "--json")
    assert result.returncode == 0
    assert json.loads(result.stdout)["plugins"][0]["classification"] == "MISSING"
