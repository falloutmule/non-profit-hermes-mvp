#!/usr/bin/env python
"""Read-only comparison of canonical CLEANUP-004 plugins with an installed root."""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
from pathlib import Path

LIVE_ROOT = Path.home() / "AppData" / "Local" / "hermes" / "plugins"
VALID = {"MATCH", "EXPECTED DERIVATION", "EXPLAINED MUTABLE STATE", "UNEXPLAINED DRIFT", "MISSING", "UNTESTED"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, pattern.replace("/**", "/*")) for pattern in patterns)


def inspect_plugin(repo: Path, installed_root: Path, plugin: dict) -> dict:
    name, directory = plugin["name"], plugin["directory"]
    canonical = repo / "runtime_plugins" / directory
    installed = installed_root / directory
    expected = {entry["path"]: entry["sha256"] for entry in plugin["files"]}
    mutable = plugin.get("mutable_paths", [])
    result = {"name": name, "directory": directory, "classification": "MATCH", "details": {"missing": [], "unexplained": [], "expected_derivations": [], "mutable_state": []}}
    if not canonical.is_dir() or not installed.is_dir():
        result["classification"] = "MISSING"
        result["details"]["missing"].append("canonical directory" if not canonical.is_dir() else "installed directory")
        return result
    for relative, wanted in expected.items():
        source = canonical / relative
        actual = installed / relative
        if not source.is_file() or not actual.is_file():
            result["details"]["missing"].append(relative)
        elif digest(source) != wanted:
            result["details"]["unexplained"].append(f"canonical manifest mismatch: {relative}")
        elif digest(actual) != wanted:
            result["details"]["unexplained"].append(relative)
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
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true", help="return 1 for missing, unexplained drift, or untested plugins")
    args = parser.parse_args()
    manifest_path = args.repo_root / "RUNTIME_PLUGIN_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    plugins = [inspect_plugin(args.repo_root, args.installed_root, item) for item in manifest["plugins"]]
    payload = {"repo_root": str(args.repo_root), "installed_root": str(args.installed_root), "read_only": True, "plugins": plugins}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for item in plugins:
            print(f"{item['name']}: {item['classification']}")
            for label, entries in item["details"].items():
                for entry in entries:
                    print(f"  {label}: {entry}")
    bad = {"MISSING", "UNEXPLAINED DRIFT", "UNTESTED"}
    return 1 if args.strict and any(item["classification"] in bad for item in plugins) else 0

if __name__ == "__main__":
    raise SystemExit(main())
