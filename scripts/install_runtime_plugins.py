#!/usr/bin/env python
"""Deliberate, dry-run-by-default installer for canonical CLEANUP-004 plugins."""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

LIVE_ROOT = (Path.home() / "AppData" / "Local" / "hermes" / "plugins").resolve()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, pattern.replace("/**", "/*")) for pattern in patterns)


def verify(repo: Path, manifest: dict) -> None:
    for plugin in manifest["plugins"]:
        root = repo / "runtime_plugins" / plugin["directory"]
        for entry in plugin["files"]:
            path = root / entry["path"]
            if not path.is_file() or digest(path) != entry["sha256"]:
                raise ValueError(f"manifest verification failed: {plugin['name']}/{entry['path']}")


def git_is_dirty(repo: Path) -> bool:
    result = subprocess.run(["git", "status", "--porcelain"], cwd=repo, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError("cannot determine Git cleanliness")
    return bool(result.stdout.strip())


def copy_mutable(existing: Path, staging: Path, patterns: list[str]) -> None:
    if not existing.is_dir():
        return
    for item in existing.rglob("*"):
        if item.is_file() and matches(item.relative_to(existing).as_posix(), patterns):
            destination = staging / item.relative_to(existing)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, destination)


def build_staging(source: Path, existing: Path, parent: Path, mutable: list[str]) -> Path:
    stage = Path(tempfile.mkdtemp(prefix=".cleanup_004_stage_", dir=parent))
    try:
        shutil.copytree(source, stage, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        copy_mutable(existing, stage, mutable)
        return stage
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def atomic_install(source: Path, target: Path, backup_root: Path, mutable: list[str]) -> Path | None:
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = build_staging(source, target, target.parent, mutable)
    backup = None
    try:
        if target.exists():
            backup_root.mkdir(parents=True, exist_ok=True)
            backup = backup_root / f"{target.name}.{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
            counter = 0
            while backup.exists():
                counter += 1
                backup = backup_root / f"{target.name}.{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.{counter}"
            os.replace(target, backup)
        os.replace(stage, target)
        return backup
    except Exception:
        if backup is not None and backup.exists() and not target.exists():
            os.replace(backup, target)
        raise
    finally:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Install canonical runtime plugins only with explicit consent")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--target-root", type=Path, help="required destination plugin root for --apply")
    parser.add_argument("--apply", action="store_true", help="perform writes; omit for dry-run")
    parser.add_argument("--live", action="store_true", help="permit a live Hermes plugin root (never implied)")
    parser.add_argument("--allow-dirty-git", action="store_true", help="override dirty-worktree protection")
    args = parser.parse_args()
    repo = args.repo_root.resolve()
    manifest = json.loads((repo / "RUNTIME_PLUGIN_MANIFEST.json").read_text(encoding="utf-8"))
    try:
        verify(repo, manifest)
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not args.apply:
        print("DRY-RUN: manifest verified; no files will be written.")
        for plugin in manifest["plugins"]:
            print(f"would install {plugin['directory']}")
        return 0
    if args.target_root is None:
        print("--apply requires an explicit --target-root", file=sys.stderr)
        return 2
    target_root = args.target_root.resolve()
    if target_root == LIVE_ROOT and not args.live:
        print("refusing live Hermes plugin root without separate --live", file=sys.stderr)
        return 2
    try:
        if not args.allow_dirty_git and git_is_dirty(repo):
            print("refusing dirty Git worktree; use --allow-dirty-git only for an intentional temporary proof", file=sys.stderr)
            return 2
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    for plugin in manifest["plugins"]:
        source = repo / "runtime_plugins" / plugin["directory"]
        backup = atomic_install(source, target_root / plugin["directory"], target_root / ".cleanup_004_backups", plugin.get("mutable_paths", []))
        print(f"INSTALLED {plugin['directory']} backup={backup or 'none'}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
