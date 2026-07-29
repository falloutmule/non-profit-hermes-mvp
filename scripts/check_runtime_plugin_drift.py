#!/usr/bin/env python
"""Read-only comparison of canonical CLEANUP-004 plugins with an installed root."""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import subprocess
from pathlib import Path, PurePosixPath

LIVE_ROOT = Path.home() / "AppData" / "Local" / "hermes" / "plugins"
VALID = {"MATCH", "EXPECTED DERIVATION", "EXPLAINED MUTABLE STATE", "UNEXPLAINED DRIFT", "MISSING", "UNTESTED"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_source_bytes(repo: Path, source: Path) -> bytes:
    """Return a tracked source identity while allowing only Git's exact CRLF checkout form."""
    checkout = source.read_bytes()
    try:
        relative = source.relative_to(repo).as_posix()
    except ValueError:
        return checkout
    try:
        tracked = subprocess.run(
            ["git", "-C", str(repo), "show", f"HEAD:{relative}"],
            capture_output=True,
            check=False,
        )
    except OSError:
        return checkout
    if tracked.returncode != 0:
        return checkout
    if checkout == tracked.stdout:
        return tracked.stdout
    if b"\x0d" not in tracked.stdout and checkout == tracked.stdout.replace(b"\x0a", b"\x0d\x0a"):
        return tracked.stdout
    return checkout


def matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, pattern.replace("/**", "/*")) for pattern in patterns)


def source_root(repo: Path, plugin: dict) -> tuple[Path, str]:
    source = plugin.get("source", f"runtime_plugins/{plugin['directory']}")
    if not isinstance(source, str) or not source or "\\" in source:
        raise ValueError("unsafe canonical source")
    relative = PurePosixPath(source)
    if (
        relative.is_absolute()
        or relative.as_posix() != source
        or any(part in {"", ".", ".."} for part in relative.parts)
        or (relative.parts and ":" in relative.parts[0])
    ):
        raise ValueError("unsafe canonical source")
    candidate = (repo / Path(*relative.parts)).resolve()
    try:
        candidate.relative_to(repo.resolve())
    except ValueError as exc:
        raise ValueError("unsafe canonical source") from exc
    return candidate, source


def plugin_manifest_identity(path: Path) -> tuple[str | None, str | None]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values.get("name"), values.get("version")


def inspect_plugin(repo: Path, installed_root: Path, plugin: dict) -> dict:
    name, directory = plugin["name"], plugin["directory"]
    try:
        canonical, source = source_root(repo, plugin)
        source_error = None
    except ValueError as exc:
        canonical, source, source_error = repo, "<invalid>", str(exc)
    installed = installed_root / directory
    expected = {entry["path"]: entry["sha256"] for entry in plugin["files"]}
    mutable = plugin.get("mutable_paths", [])
    result = {
        "name": name,
        "identity": name,
        "version": plugin.get("version"),
        "source": source,
        "role": plugin.get("role", "compatibility"),
        "directory": directory,
        "read_only": True,
        "classification": "MATCH",
        "details": {"missing": [], "unexplained": [], "expected_derivations": [], "mutable_state": []},
    }
    if source_error:
        result["classification"] = "UNEXPLAINED DRIFT"
        result["details"]["unexplained"].append(source_error)
        return result
    if not canonical.is_dir() or not installed.is_dir():
        result["classification"] = "MISSING"
        result["details"]["missing"].append("canonical directory" if not canonical.is_dir() else "installed directory")
        return result
    for relative, wanted in expected.items():
        source = canonical / relative
        actual = installed / relative
        if not source.is_file() or not actual.is_file():
            result["details"]["missing"].append(relative)
        elif hashlib.sha256(canonical_source_bytes(repo, source)).hexdigest() != wanted:
            result["details"]["unexplained"].append(f"canonical manifest mismatch: {relative}")
        elif digest(actual) != wanted:
            result["details"]["unexplained"].append(relative)
    plugin_yaml = canonical / "plugin.yaml"
    if plugin_yaml.is_file() and plugin.get("version") is not None:
        identity, version = plugin_manifest_identity(plugin_yaml)
        if identity != plugin.get("name") or version != plugin.get("version"):
            result["details"]["unexplained"].append("canonical plugin manifest identity/version mismatch")
    for candidate in installed.rglob("*"):
        if not candidate.is_file():
            continue
        relative = candidate.relative_to(installed).as_posix()
        if relative in expected:
            continue
        if relative.startswith("__pycache__/") or relative.endswith(".pyc"):
            result["details"]["expected_derivations"].append(relative)
        elif matches(relative, mutable):
            result["details"]["mutable_state"].append(relative)
        else:
            result["details"]["unexplained"].append(f"extra: {relative}")
    for key in result["details"]:
        result["details"][key].sort()
    if result["details"]["missing"]:
        result["classification"] = "MISSING"
    elif result["details"]["unexplained"]:
        result["classification"] = "UNEXPLAINED DRIFT"
    elif result["details"]["mutable_state"]:
        result["classification"] = "EXPLAINED MUTABLE STATE"
    elif result["details"]["expected_derivations"]:
        result["classification"] = "EXPECTED DERIVATION"
    elif plugin.get("test_status") == "untested":
        result["classification"] = "UNTESTED"
    assert result["classification"] in VALID
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only runtime plugin drift checker")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--installed-root", type=Path, default=LIVE_ROOT)
    parser.add_argument("--mode", choices=("unified", "legacy", "all"), help="plugin set (default: manifest default_mode)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true", help="return 1 for missing, unexplained drift, or untested plugins")
    args = parser.parse_args()
    manifest_path = args.repo_root / "RUNTIME_PLUGIN_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mode = args.mode or manifest.get("default_mode", "legacy")
    role = {"unified": "primary", "legacy": "compatibility"}.get(mode)
    selected = manifest["plugins"] if role is None else [
        item for item in manifest["plugins"] if item.get("role", "compatibility") == role
    ]
    plugins = [inspect_plugin(args.repo_root, args.installed_root, item) for item in selected]
    payload = {
        "manifest_version": manifest.get("version"),
        "mode": mode,
        "repo_root": str(args.repo_root),
        "installed_root": str(args.installed_root),
        "read_only": True,
        "plugins": plugins,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"mode={mode} manifest_version={manifest.get('version')} read_only=true")
        for item in plugins:
            print(f"{item['name']}: {item['classification']}")
            for label, entries in item["details"].items():
                for entry in entries:
                    print(f"  {label}: {entry}")
    bad = {"MISSING", "UNEXPLAINED DRIFT", "UNTESTED"}
    return 1 if args.strict and any(item["classification"] in bad for item in plugins) else 0

if __name__ == "__main__":
    raise SystemExit(main())
