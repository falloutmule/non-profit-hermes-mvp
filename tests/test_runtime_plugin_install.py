"""Offline tests for CLEANUP-004's explicit, non-live runtime-plugin installer."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install_runtime_plugins.py"


def run_git(cmd: list[str], repo: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, cwd=repo, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"git command failed: {' '.join(cmd)}\n{result.stderr.strip()}")
    return result


def make_fixture(tmp_path: Path, *, autocrlf: bool = False, checkout_newline: bytes = b"\n") -> Path:
    repo = tmp_path / "repo"
    plugin = repo / "runtime_plugins" / "non-profit-hermes-demo"
    plugin.mkdir(parents=True)

    files = {
        "plugin.yaml": "name: demo\n",
        "__init__.py": "VALUE = 1\n",
    }
    for name, body in files.items():
        (plugin / name).write_bytes(body.encode("utf-8").replace(b"\n", checkout_newline))

    run_git(["git", "init"], repo)
    run_git(["git", "config", "user.name", "runtime plugin fixture"], repo)
    run_git(["git", "config", "user.email", "fixture@example.com"], repo)
    if autocrlf:
        run_git(["git", "config", "core.autocrlf", "true"], repo)

    run_git(["git", "add", "runtime_plugins"], repo)
    run_git(["git", "commit", "-m", "fixture runtime plugins"], repo)

    manifest_files = []
    for name in files:
        blob = subprocess.check_output(["git", "-C", str(repo), "show", f"HEAD:runtime_plugins/non-profit-hermes-demo/{name}"])
        manifest_files.append({"path": name, "sha256": hashlib.sha256(blob).hexdigest()})

    manifest = {
        "version": 1,
        "plugins": [
            {
                "name": "demo",
                "directory": "non-profit-hermes-demo",
                "files": manifest_files,
                "mutable_paths": ["state.json"],
            }
        ],
    }
    (repo / "RUNTIME_PLUGIN_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    run_git(["git", "add", "RUNTIME_PLUGIN_MANIFEST.json"], repo)
    run_git(["git", "commit", "-m", "fixture manifest"], repo)
    return repo


def make_v2_fixture(tmp_path: Path) -> Path:
    repo = make_fixture(tmp_path)
    unified = repo / "plugins" / "non-profit-hermes"
    unified.mkdir(parents=True)
    unified_files = {
        "plugin.yaml": "name: non-profit-hermes\nversion: 1.0.0\n",
        "__init__.py": "VALUE = 'unified'\n",
        "commands.py": "COMMANDS = ('demo',)\n",
    }
    for name, body in unified_files.items():
        (unified / name).write_text(body, encoding="utf-8")

    legacy = repo / "runtime_plugins" / "non-profit-hermes-demo"
    (legacy / "plugin.yaml").write_text(
        "name: non-profit-hermes-demo\nversion: 1.0.0\n",
        encoding="utf-8",
    )
    run_git(["git", "add", "plugins", "runtime_plugins"], repo)
    run_git(["git", "commit", "-m", "add unified fixture source"], repo)

    def files_for(source: str, names: tuple[str, ...]) -> list[dict[str, str]]:
        return [
            {
                "path": name,
                "sha256": hashlib.sha256(
                    subprocess.check_output(["git", "-C", str(repo), "show", f"HEAD:{source}/{name}"])
                ).hexdigest(),
            }
            for name in names
        ]

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
                "files": files_for(
                    "plugins/non-profit-hermes",
                    ("__init__.py", "commands.py", "plugin.yaml"),
                ),
                "mutable_paths": ["state.json"],
            },
            {
                "name": "non-profit-hermes-demo",
                "source": "runtime_plugins/non-profit-hermes-demo",
                "directory": "non-profit-hermes-demo",
                "role": "compatibility",
                "version": "1.0.0",
                "commands": ["demo"],
                "files": files_for(
                    "runtime_plugins/non-profit-hermes-demo",
                    ("__init__.py", "plugin.yaml"),
                ),
                "mutable_paths": ["state.json"],
            },
        ],
    }
    (repo / "RUNTIME_PLUGIN_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    run_git(["git", "add", "RUNTIME_PLUGIN_MANIFEST.json"], repo)
    run_git(["git", "commit", "-m", "upgrade fixture manifest"], repo)
    return repo


def run_installer(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(INSTALLER), "--repo-root", str(repo), *args], text=True, capture_output=True, check=False)


def test_v2_default_dry_run_selects_only_unified_source(tmp_path: Path):
    repo = make_v2_fixture(tmp_path)
    target = tmp_path / "target"
    result = run_installer(repo, "--target-root", str(target))
    assert result.returncode == 0, result.stderr
    assert "mode=unified" in result.stdout
    assert "would install non-profit-hermes" in result.stdout
    assert "non-profit-hermes-demo" not in result.stdout
    assert not target.exists()


def test_legacy_mode_dry_run_selects_only_compatibility_sources(tmp_path: Path):
    repo = make_v2_fixture(tmp_path)
    target = tmp_path / "target"
    result = run_installer(repo, "--mode", "legacy", "--target-root", str(target))
    assert result.returncode == 0, result.stderr
    assert "mode=legacy" in result.stdout
    assert "would install non-profit-hermes-demo" in result.stdout
    assert "would install non-profit-hermes\n" not in result.stdout
    assert not target.exists()


def test_manifest_rejects_unsafe_absolute_traversal_or_unnormalized_source(tmp_path: Path):
    repo = make_v2_fixture(tmp_path)
    manifest_path = repo / "RUNTIME_PLUGIN_MANIFEST.json"
    original = json.loads(manifest_path.read_text(encoding="utf-8"))
    unsafe_sources = (
        str((repo / "plugins" / "non-profit-hermes").resolve()),
        "plugins/../plugins/non-profit-hermes",
        "plugins\\non-profit-hermes",
    )

    for source in unsafe_sources:
        manifest = json.loads(json.dumps(original))
        manifest["plugins"][0]["source"] = source
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        result = run_installer(repo, "--dry-run")
        assert result.returncode == 2
        assert "unsafe plugin source" in result.stderr


def test_manifest_identity_and_version_must_match_plugin_yaml(tmp_path: Path):
    repo = make_v2_fixture(tmp_path)
    manifest_path = repo / "RUNTIME_PLUGIN_MANIFEST.json"
    original = json.loads(manifest_path.read_text(encoding="utf-8"))

    for key, value in (("name", "wrong-plugin"), ("version", "9.9.9")):
        manifest = json.loads(json.dumps(original))
        manifest["plugins"][0][key] = value
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        result = run_installer(repo, "--dry-run")
        assert result.returncode == 2
        assert "plugin manifest identity/version mismatch" in result.stderr


def test_mode_selection_fails_closed_for_duplicate_command_exposure(tmp_path: Path):
    repo = make_v2_fixture(tmp_path)
    manifest_path = repo / "RUNTIME_PLUGIN_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["plugins"][1]["role"] = "primary"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = run_installer(repo, "--dry-run")
    assert result.returncode == 2
    assert "duplicate command exposure" in result.stderr


def test_default_is_dry_run_and_does_not_create_target(tmp_path: Path):
    repo = make_fixture(tmp_path)
    target = tmp_path / "target"
    result = run_installer(repo, "--target-root", str(target))
    assert result.returncode == 0, result.stderr
    assert "DRY-RUN" in result.stdout
    assert not target.exists()


def test_explicit_dry_run_flag_is_no_op(tmp_path: Path):
    repo = make_fixture(tmp_path)
    target = tmp_path / "target"
    result = run_installer(repo, "--dry-run", "--target-root", str(target))
    assert result.returncode == 0, result.stderr
    assert "DRY-RUN" in result.stdout
    assert not target.exists()


def test_verify_uses_git_blobs_with_crlf_checkout(tmp_path: Path):
    repo = make_fixture(tmp_path, autocrlf=True, checkout_newline=b"\r\n")
    target = tmp_path / "target"
    result = run_installer(repo, "--dry-run", "--target-root", str(target))
    assert result.returncode == 0, result.stderr
    assert "would install non-profit-hermes-demo" in result.stdout


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


def test_apply_rejects_dirty_worktree_without_override(tmp_path: Path):
    repo = make_fixture(tmp_path)
    target = tmp_path / "target"
    plugin_file = repo / "runtime_plugins" / "non-profit-hermes-demo" / "__init__.py"
    plugin_file.write_text("VALUE = 2\n", encoding="utf-8")
    result = run_installer(repo, "--apply", "--target-root", str(target))
    assert result.returncode != 0
    assert "refusing dirty Git worktree" in result.stderr


def test_apply_rejects_live_root_without_live_flag(tmp_path: Path):
    repo = make_fixture(tmp_path)
    live = Path.home() / "AppData" / "Local" / "hermes" / "plugins"
    result = run_installer(repo, "--apply", "--target-root", str(live), "--allow-dirty-git")
    assert result.returncode != 0
    assert "--live" in result.stderr

def test_manifest_mismatch_is_rejected(tmp_path: Path):
    repo = make_fixture(tmp_path)
    target = tmp_path / "target"
    manifest = json.loads((repo / "RUNTIME_PLUGIN_MANIFEST.json").read_text(encoding="utf-8"))
    manifest["plugins"][0]["files"][0]["sha256"] = "0" * 64
    (repo / "RUNTIME_PLUGIN_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    result = run_installer(repo, "--dry-run", "--target-root", str(target))
    assert result.returncode != 0
    assert "manifest verification failed" in result.stderr
