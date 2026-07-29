"""Fail-closed scan of tracked Git content for publication-boundary violations.

The checker reads Git objects only. Findings contain stable codes and repository
paths, never matched values, so it is safe to run in release preflight and CI.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Iterable


_RAW_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("TELEGRAM_BOT_TOKEN", re.compile(r"(?<![A-Za-z0-9_])\d{8,10}:[A-Za-z0-9_-]{30,}")),
    ("GOOGLE_TOKEN", re.compile(r"(?<![A-Za-z0-9_])(?:ya29\.|1//)[A-Za-z0-9_-]{12,}")),
    ("GOOGLE_API_KEY", re.compile(r"(?<![A-Za-z0-9_])AIza[A-Za-z0-9_-]{20,}")),
    ("TELEGRAM_PRIVATE_ID", re.compile(r"(?<!\d)-100\d{8,}(?!\d)")),
    (
        "AUTHORIZATION_VALUE",
        re.compile(r"(?i)authorization\s*[:=]\s*(?:bearer\s+)?[A-Za-z0-9._-]{12,}"),
    ),
    (
        "CLIENT_SECRET_VALUE",
        re.compile(r"(?i)\bclient_secret[\"']?\s*:\s*[\"'][A-Za-z0-9._-]{12,}"),
    ),
    ("PRIVATE_KEY", re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----")),
)
# JSON and Markdown evidence can represent Windows separators as either one
# literal backslash or a doubled JSON escape, so accept both forms.
_WINDOWS_USER_HOME = re.compile(
    r"(?i)(?:[A-Z]:[\\/]{1,2}|/)(?:Users)[\\/]{1,2}([^\\/\s<>]+)"
)
_POSIX_USER_HOME = re.compile(r"(?i)/home/([^/\s<>]+)")
_PLACEHOLDER_USER_NAMES = frozenset({"user", "username", "your-user", "example"})


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
    ).stdout


def _tracked_paths(repo: Path, revision: str) -> Iterable[str]:
    for raw_path in _git(repo, "ls-tree", "-r", "-z", "--name-only", revision).split(b"\0"):
        if raw_path:
            yield raw_path.decode("utf-8", errors="surrogateescape")


def _has_real_user_home(text: str) -> bool:
    user_names = [*(_WINDOWS_USER_HOME.findall(text)), *(_POSIX_USER_HOME.findall(text))]
    return any(
        re.fullmatch(r"[A-Za-z0-9._-]+", name)
        and name.casefold() not in _PLACEHOLDER_USER_NAMES
        for name in user_names
    )


def scan_git_commit(repo: Path, revision: str = "HEAD") -> list[dict[str, str]]:
    """Return secret-free `{code, path}` findings for an exact tracked revision."""
    findings: list[dict[str, str]] = []
    for relative_path in _tracked_paths(repo, revision):
        # Test fixtures intentionally exercise credential-shaped redaction. They do
        # not belong to the runtime/distribution publication boundary.
        if relative_path.startswith("tests/"):
            continue
        text = _git(repo, "show", f"{revision}:{relative_path}").decode(
            "utf-8", errors="replace"
        )
        codes: set[str] = set()
        if _has_real_user_home(text):
            codes.add("WINDOWS_USER_HOME_PATH")
        for code, pattern in _RAW_PATTERNS:
            if pattern.search(text):
                codes.add(code)
        findings.extend({"code": code, "path": relative_path} for code in sorted(codes))
    return sorted(findings, key=lambda item: (item["path"], item["code"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--revision", default="HEAD")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    findings = scan_git_commit(args.repo, args.revision)
    if args.json:
        print(json.dumps({"findings": findings}, sort_keys=True))
    else:
        for finding in findings:
            print(f"{finding['code']} {finding['path']}")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
