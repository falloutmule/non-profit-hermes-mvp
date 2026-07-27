#!/usr/bin/env python
"""Prepare a secret-free, disposable CI runtime for offline tests only."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "clean_install_acceptance"
FIXTURE_SPECS = (
    (
        "event_plugin",
        Path("plugins/non-profit-hermes-event/__init__.py"),
        Path("hermes-home/AppData/Local/hermes/plugins/non-profit-hermes-event/__init__.py"),
    ),
    (
        "google_api",
        Path("google-workspace/scripts/google_api.py"),
        Path("google-workspace/scripts/google_api.py"),
    ),
    (
        "hermes_home",
        Path("google-workspace/scripts/_hermes_home.py"),
        Path("google-workspace/scripts/_hermes_home.py"),
    ),
)
PRIVATE_PATTERNS = (
    ("RAW_TELEGRAM_BOT_TOKEN", re.compile(rb"(?<![A-Za-z0-9_])\d{8,10}:[A-Za-z0-9_-]{30,}")),
    ("RAW_GOOGLE_TOKEN", re.compile(rb"(?<![A-Za-z0-9_])(?:ya29\.|1//)[A-Za-z0-9_-]{12,}")),
    ("RAW_GOOGLE_API_KEY", re.compile(rb"(?<![A-Za-z0-9_])AIza[A-Za-z0-9_-]{20,}")),
    ("RAW_TELEGRAM_PRIVATE_ID", re.compile(rb"(?<!\d)-100\d{8,}(?!\d)")),
    ("RAW_TELEGRAM_NUMERIC_ID", re.compile(rb"(?i)(?<![A-Za-z0-9_])telegram:\d+(?!\d)")),
    ("RAW_AUTHORIZATION", re.compile(rb"(?i)authorization\s*[:=]\s*(?:bearer\s+)?[A-Za-z0-9._-]{12,}")),
    ("RAW_CLIENT_SECRET", re.compile(rb"(?i)\bclient_secret[\"']?\s*:\s*[\"'][A-Za-z0-9._-]{12,}")),
)


class PreparationError(RuntimeError):
    """Stable, secret-safe CI preparation failure."""


def destination_under(root: Path, relative: Path) -> Path:
    root = root.resolve()
    if relative.is_absolute() or ".." in relative.parts:
        raise PreparationError("DESTINATION_ESCAPE")
    destination = (root / relative).resolve()
    try:
        destination.relative_to(root)
    except ValueError as exc:
        raise PreparationError("DESTINATION_ESCAPE") from exc
    return destination


def private_findings(source: Path) -> dict[str, int]:
    data = source.read_bytes()
    return {
        code: count
        for code, pattern in PRIVATE_PATTERNS
        if (count := len(pattern.findall(data)))
    }


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def event_source_link(event_plugin: Path) -> str:
    match = re.search(r"source_link\s*=\s*[\"']([^\"']+)[\"']", event_plugin.read_text(encoding="utf-8"))
    if match is None or not match.group(1).startswith("telegram:"):
        raise PreparationError("EVENT_PLUGIN_SOURCE_LINK_INVALID")
    return match.group(1)


def runtime_python_supported(version: str) -> bool:
    try:
        major, minor = (int(part) for part in version.split(".", maxsplit=2)[:2])
    except ValueError:
        return False
    return (major, minor) in {(3, 11), (3, 12), (3, 13)}


def prepare(
    destination: Path,
    *,
    fixture_root: Path = FIXTURE_ROOT,
    fixture_specs: Iterable[tuple[str, Path, Path]] = FIXTURE_SPECS,
) -> dict[str, object]:
    """Copy only audited test fixtures into an empty caller-selected root."""
    destination = destination.resolve()
    fixture_root = fixture_root.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise PreparationError("DESTINATION_NOT_EMPTY")
    destination.mkdir(parents=True, exist_ok=True)

    evidence: dict[str, dict[str, object]] = {}
    for name, source_relative, destination_relative in fixture_specs:
        source = (fixture_root / source_relative).resolve()
        try:
            source.relative_to(fixture_root)
        except ValueError as exc:
            raise PreparationError("FIXTURE_SOURCE_ESCAPE") from exc
        if not source.is_file():
            raise PreparationError("FIXTURE_SOURCE_MISSING")
        findings = private_findings(source)
        if findings:
            raise PreparationError("FIXTURE_PRIVATE_MATERIAL")
        target = destination_under(destination, destination_relative)
        if target.exists():
            raise PreparationError("FIXTURE_DESTINATION_COLLISION")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        source_hash = sha256(source)
        destination_hash = sha256(target)
        if source_hash != destination_hash:
            raise PreparationError("FIXTURE_HASH_MISMATCH")
        evidence[name] = {
            "source": str(source),
            "destination": str(target),
            "source_sha256": source_hash,
            "destination_sha256": destination_hash,
            "private_findings": findings,
        }

    home = destination_under(destination, Path("hermes-home"))
    hermes_home = destination_under(home, Path("AppData/Local/hermes"))
    google_workspace_scripts = destination_under(destination, Path("google-workspace/scripts"))
    external_cwd = destination_under(destination, Path("external-cwd"))
    for path in (home, hermes_home, google_workspace_scripts, external_cwd):
        path.mkdir(parents=True, exist_ok=True)
    event_plugin = Path(evidence["event_plugin"]["destination"])
    return {
        "home": str(home),
        "hermes_home": str(hermes_home),
        "google_workspace_scripts": str(google_workspace_scripts),
        "external_cwd": str(external_cwd),
        "event_source_link": event_source_link(event_plugin),
        "fixtures": evidence,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    evidence = prepare(args.destination)
    if args.json:
        print(json.dumps(evidence, sort_keys=True))
    else:
        print("prepared secret-free CI test runtime")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
