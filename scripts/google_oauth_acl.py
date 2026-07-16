"""Dependency-free, redacted semantic ACL repair helpers for Windows.

Only ``icacls`` metadata is inspected.  File contents are written or moved by the
explicit preparation/promotion operations and are never included in snapshots or
exceptions.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Final, TypeAlias


_MARKER_RE: Final[re.Pattern[str]] = re.compile(r"\(([^()]*)\)")
_ACE_RE: Final[re.Pattern[str]] = re.compile(r":(?=\s*\()")
_HEADER_PREFIX_RE: Final[re.Pattern[str]] = re.compile(r"^(?:[A-Za-z]:\\|\\\\).*?(?=\s+[^:]+:\()")


class AclRepairError(RuntimeError):
    """Redacted, stable failure category for ACL repair operations."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"ACL_REPAIR_{code}")


@dataclass(frozen=True, order=True)
class AclAce:
    """Canonical ACE metadata; no path or file content is retained."""

    principal: str
    markers: tuple[str, ...]

    @property
    def effect(self) -> str:
        return "DENY" if "DENY" in self.markers else "ALLOW"

    @property
    def inheritance(self) -> str:
        return "INHERITED" if "I" in self.markers else "EXPLICIT"


AclSnapshot: TypeAlias = tuple[AclAce, ...]


def _canonical_principal(value: str) -> str:
    # icacls indentation and wrapping are formatting.  Preserve principal spelling
    # while removing only whitespace that cannot be semantic in this output format.
    return " ".join(value.strip().split())


def parse_icacls_output(output: str) -> AclSnapshot:
    """Parse icacls text into a path-independent, sorted semantic snapshot."""
    lines = output.splitlines()
    aces: list[AclAce] = []
    for line in lines:
        text = line.strip()
        if not text:
            continue
        header_prefix = _HEADER_PREFIX_RE.match(text)
        if header_prefix:
            text = text[header_prefix.end() :].strip()
        if _ACE_RE.search(text) is None:
            continue
        marker_colon = list(_ACE_RE.finditer(text))[-1]
        principal = _canonical_principal(text[: marker_colon.start()])
        marker_text = text[marker_colon.end() :]
        markers = tuple(sorted(token.strip().upper() for token in _MARKER_RE.findall(marker_text) if token.strip()))
        if not principal or not markers:
            continue
        aces.append(AclAce(principal=principal, markers=markers))
    return tuple(sorted(aces))


def _run_icacls(path: Path, *arguments: str) -> str:
    try:
        completed = subprocess.run(
            ["icacls", os.fspath(path), *arguments],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (FileNotFoundError, OSError) as exc:
        raise AclRepairError("ICACLS_UNAVAILABLE") from exc
    if completed.returncode != 0:
        raise AclRepairError("ICACLS_FAILED")
    return completed.stdout


def capture_acl(path: os.PathLike[str] | str, *, runner: Callable[..., str] = _run_icacls) -> AclSnapshot:
    """Capture only the semantic ACL metadata reported by icacls."""
    return parse_icacls_output(runner(Path(path)))


def acl_equivalent(
    reference: os.PathLike[str] | str,
    candidate: os.PathLike[str] | str,
    *,
    snapshotter: Callable[[os.PathLike[str] | str], AclSnapshot] = capture_acl,
) -> bool:
    """Compare canonical semantic ACLs, never raw command output."""
    return snapshotter(reference) == snapshotter(candidate)


def prepare_candidate(
    reference: os.PathLike[str] | str,
    candidate: os.PathLike[str] | str,
    data: bytes,
    *,
    runner: Callable[..., str] = _run_icacls,
    snapshotter: Callable[[os.PathLike[str] | str], AclSnapshot] | None = None,
) -> Path:
    """Write synthetic candidate bytes, enable safe inheritance, and fail closed."""
    reference_path = Path(reference)
    candidate_path = Path(candidate)
    try:
        candidate_path.write_bytes(data)
        # Enabling inheritance is safe for a newly-created file and avoids copying
        # opaque security-descriptor text.  Equality remains the mandatory gate.
        runner(candidate_path, "/inheritance:e")
        compare = snapshotter or (lambda path: capture_acl(path, runner=runner))
        if compare(reference_path) != compare(candidate_path):
            raise AclRepairError("ACL_MISMATCH")
    except AclRepairError:
        try:
            candidate_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    except OSError as exc:
        try:
            candidate_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise AclRepairError("CANDIDATE_WRITE_FAILED") from exc
    return candidate_path


def _new_backup_path(operational: Path) -> Path:
    fd, raw = tempfile.mkstemp(prefix=f".{operational.name}.", suffix=".acl-backup", dir=operational.parent)
    os.close(fd)
    path = Path(raw)
    path.unlink()
    return path


def atomic_promote(
    operational: os.PathLike[str] | str,
    candidate: os.PathLike[str] | str,
    *,
    snapshotter: Callable[[os.PathLike[str] | str], AclSnapshot] = capture_acl,
    replace: Callable[[str | os.PathLike[str], str | os.PathLike[str]], None] = os.replace,
    backup_path: os.PathLike[str] | str | None = None,
) -> Path:
    """Promote an ACL-equivalent candidate with an atomic, rollback-capable swap."""
    operational_path = Path(operational)
    candidate_path = Path(candidate)
    backup = Path(backup_path) if backup_path is not None else _new_backup_path(operational_path)
    if not operational_path.is_file() or not candidate_path.is_file():
        raise AclRepairError("PATH_NOT_REGULAR_FILE")
    if operational_path.stat().st_dev != candidate_path.stat().st_dev:
        raise AclRepairError("FILESYSTEM_MISMATCH")
    candidate_acl = snapshotter(candidate_path)
    if snapshotter(operational_path) != candidate_acl:
        raise AclRepairError("ACL_MISMATCH")

    moved_backup = False
    try:
        replace(operational_path, backup)
        moved_backup = True
        replace(candidate_path, operational_path)
        if snapshotter(operational_path) != candidate_acl:
            raise AclRepairError("PROMOTED_ACL_MISMATCH")
    except Exception as exc:
        if moved_backup:
            try:
                if operational_path.exists():
                    replace(operational_path, candidate_path)
                replace(backup, operational_path)
            except Exception as rollback_exc:
                raise AclRepairError("ROLLBACK_FAILED") from rollback_exc
        if isinstance(exc, AclRepairError):
            raise
        raise AclRepairError("PROMOTION_FAILED") from exc
    try:
        backup.unlink()
    except OSError as exc:
        raise AclRepairError("BACKUP_CLEANUP_FAILED") from exc
    return operational_path
