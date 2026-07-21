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
        "plugins": [
            {
                "name": "demo",
                "directory": "non-profit-hermes-demo",
                "files": [
                    {"path": "__init__.py", "sha256": "b6c11985b7720c15580c1b1dac6a53b12254777518f0d8ea5b6892c8e768e90e"},
                    {"path": "plugin.yaml", "sha256": "cb2d32547da87ed7b8b831d616a75f2be75eef2aee08bbb6bf9aecdf08d7f20a"},
                ],
                "mutable_paths": ["__pycache__/**"],
            }
        ],
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


def make_v2_fixture(tmp_path: Path) -> tuple[Path, Path]:
    import hashlib

    installed = tmp_path / "installed"

    def make_plugin(source: str, directory: str, files: dict[str, bytes]) -> list[dict[str, str]]:
        canonical = tmp_path / source
        target = installed / directory
        canonical.mkdir(parents=True)
        target.mkdir(parents=True)
        entries = []
        for path, content in files.items():
            (canonical / path).write_bytes(content)
            (target / path).write_bytes(content)
            entries.append({"path": path, "sha256": hashlib.sha256(content).hexdigest()})
        return entries

    unified_files = make_plugin(
        "plugins/non-profit-hermes",
        "non-profit-hermes",
        {
            "__init__.py": b"VALUE = 'unified'\n",
            "commands.py": b"COMMANDS = ('demo',)\n",
            "plugin.yaml": b"name: non-profit-hermes\nversion: 1.0.0\n",
        },
    )
    legacy_files = make_plugin(
        "runtime_plugins/non-profit-hermes-demo",
        "non-profit-hermes-demo",
        {
            "__init__.py": b"VALUE = 'legacy'\n",
            "plugin.yaml": b"name: non-profit-hermes-demo\nversion: 1.0.0\n",
        },
    )
    manifest = {
        "schema": "Non-Profit Hermes runtime plugin manifest",
        "version": 2,
        "default_mode": "unified",
        "plugins": [
            {
                "name": "non-profit-hermes",
                "source": "plugins/non-profit-hermes",
                "directory": "non-profit-hermes",
                "role": "primary",
                "version": "1.0.0",
                "commands": ["demo"],
                "files": unified_files,
                "mutable_paths": ["__pycache__/**"],
            },
            {
                "name": "non-profit-hermes-demo",
                "source": "runtime_plugins/non-profit-hermes-demo",
                "directory": "non-profit-hermes-demo",
                "role": "compatibility",
                "version": "1.0.0",
                "commands": ["demo"],
                "files": legacy_files,
                "mutable_paths": ["__pycache__/**"],
            },
        ],
    }
    (tmp_path / "RUNTIME_PLUGIN_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    return tmp_path, installed


def run_checker(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECKER), "--repo-root", str(repo), *args],
        text=True,
        capture_output=True,
        check=False,
    )


def test_v2_default_checks_only_unified_and_reports_source_role_identity(tmp_path: Path):
    repo, installed = make_v2_fixture(tmp_path)
    result = run_checker(repo, "--installed-root", str(installed), "--json", "--strict")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["manifest_version"] == 2
    assert payload["mode"] == "unified"
    assert payload["read_only"] is True
    assert len(payload["plugins"]) == 1
    assert {
        key: payload["plugins"][0][key]
        for key in ("source", "role", "identity", "version")
    } == {
        "source": "plugins/non-profit-hermes",
        "role": "primary",
        "identity": "non-profit-hermes",
        "version": "1.0.0",
    }
    assert payload["plugins"][0]["classification"] == "MATCH"


def test_legacy_and_all_modes_are_selected_read_only_audits(tmp_path: Path):
    repo, installed = make_v2_fixture(tmp_path)
    before = {
        path.relative_to(installed).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in installed.rglob("*")
        if path.is_file()
    }

    legacy = run_checker(
        repo,
        "--installed-root",
        str(installed),
        "--mode",
        "legacy",
        "--json",
        "--strict",
    )
    assert legacy.returncode == 0, legacy.stderr
    legacy_payload = json.loads(legacy.stdout)
    assert legacy_payload["mode"] == "legacy"
    assert [item["identity"] for item in legacy_payload["plugins"]] == ["non-profit-hermes-demo"]

    all_result = run_checker(
        repo,
        "--installed-root",
        str(installed),
        "--mode",
        "all",
        "--json",
    )
    assert all_result.returncode == 0, all_result.stderr
    all_payload = json.loads(all_result.stdout)
    assert all_payload["mode"] == "all"
    assert [item["identity"] for item in all_payload["plugins"]] == [
        "non-profit-hermes",
        "non-profit-hermes-demo",
    ]
    after = {
        path.relative_to(installed).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in installed.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_strict_mode_is_scoped_and_rejects_selected_mode_drift(tmp_path: Path):
    repo, installed = make_v2_fixture(tmp_path)
    legacy_file = installed / "non-profit-hermes-demo" / "__init__.py"
    legacy_file.write_text("VALUE = 'drift'\n", encoding="utf-8")

    unified = run_checker(repo, "--installed-root", str(installed), "--strict")
    assert unified.returncode == 0
    legacy = run_checker(
        repo,
        "--installed-root",
        str(installed),
        "--mode",
        "legacy",
        "--strict",
    )
    assert legacy.returncode == 1
    assert "UNEXPLAINED DRIFT" in legacy.stdout


def test_unsafe_source_is_redacted_and_strictly_rejected(tmp_path: Path):
    repo, installed = make_v2_fixture(tmp_path)
    manifest_path = repo / "RUNTIME_PLUGIN_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    private_source = "C:/private/credential-location"
    manifest["plugins"][0]["source"] = private_source
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = run_checker(repo, "--installed-root", str(installed), "--json", "--strict")
    assert result.returncode == 1
    assert private_source not in result.stdout
    plugin = json.loads(result.stdout)["plugins"][0]
    assert plugin["source"] == "<invalid>"
    assert plugin["classification"] == "UNEXPLAINED DRIFT"


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


def test_strict_fails_for_unexpected_file(tmp_path: Path):
    repo, installed = make_fixture(tmp_path)
    extra = installed / "non-profit-hermes-demo" / "unexpected.txt"
    extra.write_text("extra\n", encoding="utf-8")
    result = run_checker(repo, "--installed-root", str(installed), "--strict", "--json")
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["plugins"][0]["classification"] == "UNEXPLAINED DRIFT"
    assert "extra: unexpected.txt" in payload["plugins"][0]["details"]["unexplained"]


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
        if item.is_file():
            item.unlink()
    (installed / "non-profit-hermes-demo").rmdir()
    result = run_checker(repo, "--installed-root", str(installed), "--json")
    assert result.returncode == 0
    assert json.loads(result.stdout)["plugins"][0]["classification"] == "MISSING"
