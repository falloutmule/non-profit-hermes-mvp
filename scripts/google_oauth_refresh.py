"""Atomic, recoverable, redacted persistence for an in-memory OAuth refresh.

This module intentionally never starts a refresh or Google API call itself.  Its
caller supplies the already-loaded credential and request object.  The only
persistent authority is the operational token file; a separate candidate is
fully validated before an atomic promotion is attempted.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Final

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in __import__("sys").path:
    __import__("sys").path.insert(0, _SCRIPT_DIR)

from google_oauth_acl import AclSnapshot, capture_acl, prepare_candidate
from google_oauth_candidate_acceptance import CandidateAcceptanceMetadata, evaluate_candidate_acceptance


class RefreshPersistenceError(RuntimeError):
    """Stable, secret-free persistence failure category."""

    def __init__(self, code: str, *, rollback_code: str | None = None) -> None:
        self.code = code
        self.rollback_code = rollback_code
        message = f"REFRESH_PERSISTENCE_{code}"
        if rollback_code is not None:
            message += f"_ROLLBACK_{rollback_code}"
        super().__init__(message)


@dataclass(frozen=True)
class PreparedRefreshCandidate:
    """Private in-process persistence state; never serialize or log this object."""

    operational_token: Path
    candidate: Path
    original_bytes: bytes
    original_hash: str
    original_acl: AclSnapshot
    candidate_hash: str
    candidate_acl: AclSnapshot
    expected_scope_names: frozenset[str]
    expected_client_id: str


@dataclass(frozen=True)
class RefreshValidation:
    """Redacted validation output safe to include in evidence."""

    accepted: bool
    invariant_code: str
    checks: dict[str, bool]


@dataclass(frozen=True)
class RefreshPromotion:
    """Redacted promotion result safe to include in evidence."""

    operational_hash: str
    rollback_attempted: bool = False


CredentialLoader = Callable[[dict[str, Any], list[str]], Any]
CandidatePreparer = Callable[..., Path]
Snapshotter = Callable[[os.PathLike[str] | str], AclSnapshot]
Replacer = Callable[[str | os.PathLike[str], str | os.PathLike[str]], None]
Flusher = Callable[[Path], None]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _scope_set(value: Any) -> frozenset[str]:
    if type(value) not in (list, tuple, set, frozenset):
        return frozenset()
    if any(type(item) is not str or not item for item in value):
        return frozenset()
    return frozenset(value)


def _safe_json_object(data: bytes) -> dict[str, Any] | None:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if type(value) is dict else None


def _credential_loader(info: dict[str, Any], scopes: list[str]) -> Any:
    from google.oauth2.credentials import Credentials

    return Credentials.from_authorized_user_info(info, scopes=scopes)


def _flush_file_and_parent(path: Path) -> None:
    """Flush a file and, where the host supports it, its containing directory."""
    try:
        with path.open("rb") as handle:
            os.fsync(handle.fileno())
    except OSError as exc:
        raise RefreshPersistenceError("FILE_FLUSH_FAILED") from exc
    try:
        descriptor = os.open(os.fspath(path.parent), os.O_RDONLY)
    except OSError:
        return  # Windows commonly does not permit opening a directory this way.
    try:
        os.fsync(descriptor)
    except OSError:
        pass  # Parent directory flush is explicitly best-effort where unsupported.
    finally:
        os.close(descriptor)


def _default_candidate_path(operational: Path) -> Path:
    return operational.with_name(f".{operational.name}.refresh-candidate")


def _new_backup_path(operational: Path) -> Path:
    descriptor, raw = tempfile.mkstemp(prefix=f".{operational.name}.", suffix=".refresh-backup", dir=operational.parent)
    os.close(descriptor)
    path = Path(raw)
    path.unlink()
    return path


def _write_exact_backup(
    prepared: PreparedRefreshCandidate,
    backup: Path,
    *,
    candidate_preparer: CandidatePreparer,
    flusher: Flusher,
) -> Path:
    if backup.exists():
        raise RefreshPersistenceError("BACKUP_ALREADY_EXISTS")
    try:
        result = candidate_preparer(prepared.operational_token, backup, prepared.original_bytes)
        if Path(result) != backup or backup.read_bytes() != prepared.original_bytes:
            raise RefreshPersistenceError("BACKUP_CONTENT_MISMATCH")
        flusher(backup)
    except RefreshPersistenceError:
        raise
    except Exception as exc:
        raise RefreshPersistenceError("BACKUP_FAILED") from exc
    return backup


def _cleanup(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


class _RefreshLock:
    def __init__(self, operational: Path) -> None:
        self.path = operational.with_name(f".{operational.name}.refresh.lock")
        self._descriptor: int | None = None

    def __enter__(self) -> "_RefreshLock":
        try:
            self._descriptor = os.open(os.fspath(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(self._descriptor, b"refresh-lock\n")
            os.fsync(self._descriptor)
        except FileExistsError as exc:
            raise RefreshPersistenceError("CONCURRENT_REFRESH") from exc
        except OSError as exc:
            raise RefreshPersistenceError("LOCK_FAILED") from exc
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        if self._descriptor is not None:
            os.close(self._descriptor)
        _cleanup(self.path)


def refresh_credential_in_memory(credential: Any, request: Any) -> Any:
    """Refresh only the supplied in-memory credential; never writes a token file."""
    if not getattr(credential, "refresh_token", None):
        raise RefreshPersistenceError("REFRESH_TOKEN_MISSING")
    try:
        credential.refresh(request)
    except Exception as exc:
        raise RefreshPersistenceError("REFRESH_FAILED") from exc
    return credential


def prepare_refresh_candidate(
    operational_token: os.PathLike[str] | str,
    credential: Any,
    expected_scopes: list[str] | tuple[str, ...] | frozenset[str],
    *,
    candidate_path: os.PathLike[str] | str | None = None,
    original_hash: str | None = None,
    candidate_preparer: CandidatePreparer = prepare_candidate,
    snapshotter: Snapshotter = capture_acl,
    flusher: Flusher = _flush_file_and_parent,
) -> PreparedRefreshCandidate:
    """Serialize a refreshed credential to a separate, ACL-safe candidate only."""
    operational = Path(operational_token)
    candidate = Path(candidate_path) if candidate_path is not None else _default_candidate_path(operational)
    if candidate.exists():
        raise RefreshPersistenceError("CANDIDATE_ALREADY_EXISTS")
    try:
        original_bytes = operational.read_bytes()
        original_acl = snapshotter(operational)
    except Exception as exc:
        raise RefreshPersistenceError("OPERATIONAL_READ_FAILED") from exc
    observed_original_hash = _sha256(original_bytes)
    if original_hash is not None and original_hash != observed_original_hash:
        raise RefreshPersistenceError("OPERATIONAL_CHANGED_BEFORE_PREPARE")
    original_info = _safe_json_object(original_bytes)
    expected_client_id = original_info.get("client_id") if original_info is not None else None
    if type(expected_client_id) is not str or not expected_client_id:
        raise RefreshPersistenceError("OPERATIONAL_SERIALIZATION_INVALID")
    expected_scope_names = _scope_set(expected_scopes)
    if not expected_scope_names:
        raise RefreshPersistenceError("EXPECTED_SCOPES_INVALID")
    try:
        serialized = credential.to_json()
        parsed = json.loads(serialized)
        if type(parsed) is not dict:
            raise TypeError
        candidate_bytes = (json.dumps(parsed, indent=2, sort_keys=True) + "\n").encode("utf-8")
    except Exception as exc:
        raise RefreshPersistenceError("SERIALIZATION_FAILED") from exc
    try:
        prepared_path = candidate_preparer(operational, candidate, candidate_bytes)
        if Path(prepared_path) != candidate:
            raise RefreshPersistenceError("CANDIDATE_PREPARATION_FAILED")
        flusher(candidate)
        candidate_acl = snapshotter(candidate)
    except RefreshPersistenceError:
        _cleanup(candidate)
        raise
    except Exception as exc:
        _cleanup(candidate)
        raise RefreshPersistenceError("CANDIDATE_PREPARATION_FAILED") from exc
    if _sha256(operational.read_bytes()) != observed_original_hash:
        _cleanup(candidate)
        raise RefreshPersistenceError("OPERATIONAL_CHANGED_DURING_PREPARE")
    return PreparedRefreshCandidate(
        operational_token=operational,
        candidate=candidate,
        original_bytes=original_bytes,
        original_hash=observed_original_hash,
        original_acl=original_acl,
        candidate_hash=_sha256(candidate_bytes),
        candidate_acl=candidate_acl,
        expected_scope_names=expected_scope_names,
        expected_client_id=expected_client_id,
    )


def validate_refresh_candidate(
    prepared: PreparedRefreshCandidate,
    credential: Any,
    *,
    credential_loader: CredentialLoader = _credential_loader,
    snapshotter: Snapshotter = capture_acl,
) -> RefreshValidation:
    """Validate candidate semantics without exposing any credential value."""
    candidate_bytes = prepared.candidate.read_bytes() if prepared.candidate.is_file() else b""
    candidate_info = _safe_json_object(candidate_bytes)
    serialized_json_valid = candidate_info is not None
    serialized_field_names = frozenset(candidate_info) if candidate_info is not None else frozenset()
    loaded = credential
    if candidate_info is not None:
        try:
            loaded = credential_loader(candidate_info, sorted(prepared.expected_scope_names))
        except Exception:
            loaded = None
    granted_scopes = _scope_set(getattr(loaded, "granted_scopes", None))
    if not granted_scopes:
        granted_scopes = _scope_set(candidate_info.get("scopes") if candidate_info is not None else None)
    try:
        candidate_acl_matches = snapshotter(prepared.candidate) == prepared.candidate_acl
    except Exception:
        candidate_acl_matches = False
    metadata = CandidateAcceptanceMetadata(
        credential_valid=bool(getattr(loaded, "valid", False)),
        credential_expired=bool(getattr(loaded, "expired", True)),
        granted_scope_names=granted_scopes,
        expected_scope_names=prepared.expected_scope_names,
        client_identity_matches=bool(candidate_info and candidate_info.get("client_id") == prepared.expected_client_id),
        refresh_token_present=bool(candidate_info and candidate_info.get("refresh_token")),
        serialized_json_valid=serialized_json_valid,
        serialized_shape_expected=type(candidate_info) is dict,
        serialized_field_names=serialized_field_names,
        token_type_expected=bool(candidate_info and candidate_info.get("type") == "authorized_user"),
        candidate_acl_matches=candidate_acl_matches,
        existing_token_unchanged=_sha256(prepared.operational_token.read_bytes()) == prepared.original_hash,
    )
    evaluated = evaluate_candidate_acceptance(metadata)
    return RefreshValidation(
        accepted=bool(evaluated["accepted"]),
        invariant_code=str(evaluated["invariant_code"]),
        checks=dict(evaluated["checks"]),
    )


def rollback_refresh_promotion(
    prepared: PreparedRefreshCandidate,
    backup_path: os.PathLike[str] | str,
    *,
    replacer: Replacer = os.replace,
    snapshotter: Snapshotter = capture_acl,
    flusher: Flusher = _flush_file_and_parent,
) -> None:
    """Restore the exact pre-promotion bytes and semantic ACL, or fail distinctly."""
    backup = Path(backup_path)
    try:
        if prepared.operational_token.exists():
            replacer(prepared.operational_token, prepared.candidate)
        replacer(backup, prepared.operational_token)
        flusher(prepared.operational_token)
        if prepared.operational_token.read_bytes() != prepared.original_bytes:
            raise OSError("rollback bytes differ")
        if snapshotter(prepared.operational_token) != prepared.original_acl:
            raise OSError("rollback ACL differs")
    except Exception as exc:
        raise RefreshPersistenceError("ROLLBACK_FAILED", rollback_code="FAILED") from exc


def promote_refresh_candidate_atomically(
    prepared: PreparedRefreshCandidate,
    validation: RefreshValidation,
    *,
    backup_path: os.PathLike[str] | str | None = None,
    candidate_preparer: CandidatePreparer = prepare_candidate,
    snapshotter: Snapshotter = capture_acl,
    replacer: Replacer = os.replace,
    flusher: Flusher = _flush_file_and_parent,
    post_replace_validator: Callable[[Path], None] | None = None,
) -> RefreshPromotion:
    """Atomically promote a validated candidate and roll back every post-swap failure."""
    if not validation.accepted:
        raise RefreshPersistenceError(validation.invariant_code)
    backup = Path(backup_path) if backup_path is not None else _new_backup_path(prepared.operational_token)
    with _RefreshLock(prepared.operational_token):
        if _sha256(prepared.operational_token.read_bytes()) != prepared.original_hash:
            raise RefreshPersistenceError("OPERATIONAL_CHANGED_BEFORE_PROMOTION")
        if snapshotter(prepared.operational_token) != prepared.original_acl:
            raise RefreshPersistenceError("OPERATIONAL_ACL_CHANGED_BEFORE_PROMOTION")
        _write_exact_backup(prepared, backup, candidate_preparer=candidate_preparer, flusher=flusher)
        replaced = False
        try:
            replacer(prepared.candidate, prepared.operational_token)
            replaced = True
            flusher(prepared.operational_token)
            if _sha256(prepared.operational_token.read_bytes()) != prepared.candidate_hash:
                raise RefreshPersistenceError("PROMOTED_HASH_MISMATCH")
            if snapshotter(prepared.operational_token) != prepared.candidate_acl:
                raise RefreshPersistenceError("PROMOTED_ACL_MISMATCH")
            if post_replace_validator is not None:
                post_replace_validator(prepared.operational_token)
            backup.unlink()
            flusher(prepared.operational_token)
        except Exception as exc:
            if replaced:
                try:
                    rollback_refresh_promotion(
                        prepared,
                        backup,
                        replacer=replacer,
                        snapshotter=snapshotter,
                        flusher=flusher,
                    )
                except RefreshPersistenceError as rollback_error:
                    raise RefreshPersistenceError("POST_REPLACE_FAILED", rollback_code=rollback_error.code) from rollback_error
                if isinstance(exc, RefreshPersistenceError):
                    raise exc
                raise RefreshPersistenceError("POST_REPLACE_FAILED") from exc
            _cleanup(backup)
            if isinstance(exc, RefreshPersistenceError):
                raise
            raise RefreshPersistenceError("PROMOTION_FAILED") from exc
    return RefreshPromotion(operational_hash=prepared.candidate_hash)


def refresh_and_persist_credential(
    credential: Any,
    request: Any,
    operational_token: os.PathLike[str] | str,
    expected_scopes: list[str] | tuple[str, ...] | frozenset[str],
    *,
    candidate_path: os.PathLike[str] | str | None = None,
    backup_path: os.PathLike[str] | str | None = None,
    candidate_preparer: CandidatePreparer = prepare_candidate,
    snapshotter: Snapshotter = capture_acl,
    flusher: Flusher = _flush_file_and_parent,
    credential_loader: CredentialLoader = _credential_loader,
    replacer: Replacer = os.replace,
    post_replace_validator: Callable[[Path], None] | None = None,
) -> Any:
    """Caller integration seam: snapshot, refresh in memory, validate, then promote."""
    operational = Path(operational_token)
    try:
        original_hash = _sha256(operational.read_bytes())
    except OSError as exc:
        raise RefreshPersistenceError("OPERATIONAL_READ_FAILED") from exc
    refresh_credential_in_memory(credential, request)
    prepared = prepare_refresh_candidate(
        operational,
        credential,
        expected_scopes,
        candidate_path=candidate_path,
        original_hash=original_hash,
        candidate_preparer=candidate_preparer,
        snapshotter=snapshotter,
        flusher=flusher,
    )
    validation = validate_refresh_candidate(
        prepared,
        credential,
        credential_loader=credential_loader,
        snapshotter=snapshotter,
    )
    if not validation.accepted:
        _cleanup(prepared.candidate)
        raise RefreshPersistenceError(validation.invariant_code)
    promote_refresh_candidate_atomically(
        prepared,
        validation,
        backup_path=backup_path,
        candidate_preparer=candidate_preparer,
        snapshotter=snapshotter,
        replacer=replacer,
        flusher=flusher,
        post_replace_validator=post_replace_validator,
    )
    return credential


def refresh_evidence(
    prepared: PreparedRefreshCandidate | None, validation: RefreshValidation | None, error: RefreshPersistenceError | None = None) -> dict[str, object]:
    """Return only deterministic, secret-free status evidence."""
    return {
        "accepted": bool(validation and validation.accepted and error is None),
        "invariant_code": error.code if error is not None else (validation.invariant_code if validation else "NOT_RUN"),
        "original_hash_sha256": prepared.original_hash if prepared is not None else None,
        "candidate_hash_sha256": prepared.candidate_hash if prepared is not None else None,
        "rollback_code": error.rollback_code if error is not None else None,
    }


__all__: Final[tuple[str, ...]] = (
    "PreparedRefreshCandidate",
    "RefreshPersistenceError",
    "RefreshPromotion",
    "RefreshValidation",
    "prepare_refresh_candidate",
    "promote_refresh_candidate_atomically",
    "refresh_and_persist_credential",
    "refresh_credential_in_memory",
    "refresh_evidence",
    "rollback_refresh_promotion",
    "validate_refresh_candidate",
)
