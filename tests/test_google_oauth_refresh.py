"""Offline fake-only tests for atomic OAuth token refresh persistence."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "google_oauth_refresh.py"
SCOPES = ["scope:calendar", "scope:sheets"]


def load_module():
    spec = importlib.util.spec_from_file_location("google_oauth_refresh", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


class FakeCredential:
    def __init__(
        self,
        *,
        client_id: str = "expected-client",
        scopes: list[str] | None = None,
        refresh_token: str | None = "synthetic-refresh-token",
        valid: bool = True,
        expired: bool = False,
        refresh_error: Exception | None = None,
        serialization_error: Exception | None = None,
    ) -> None:
        self.client_id = client_id
        self.granted_scopes = list(SCOPES if scopes is None else scopes)
        self.refresh_token = refresh_token
        self.valid = valid
        self.expired = expired
        self.refresh_error = refresh_error
        self.serialization_error = serialization_error
        self.refresh_calls = 0

    def refresh(self, _request) -> None:
        self.refresh_calls += 1
        if self.refresh_error is not None:
            raise self.refresh_error

    def to_json(self) -> str:
        if self.serialization_error is not None:
            raise self.serialization_error
        return json.dumps(
            {
                "type": "authorized_user",
                "client_id": self.client_id,
                "refresh_token": self.refresh_token,
                "token": "synthetic-access-token",
                "scopes": self.granted_scopes,
                "token_uri": "https://oauth2.example/token",
            }
        )


def fake_prepare(reference, candidate, data, **_kwargs):
    del reference
    Path(candidate).write_bytes(data)
    return Path(candidate)


def snapshotter(_path):
    return ()


def no_flush(_path):
    return None


def make_prepared(refresh, tmp_path: Path, credential: FakeCredential | None = None):
    operational = tmp_path / "google_token.json"
    original = {
        "type": "authorized_user",
        "client_id": "expected-client",
        "refresh_token": "original-refresh-token",
        "token": "original-access-token",
        "scopes": SCOPES,
    }
    operational.write_text(json.dumps(original))
    credential = credential or FakeCredential()
    prepared = refresh.prepare_refresh_candidate(
        operational,
        credential,
        SCOPES,
        candidate_path=tmp_path / "candidate.json",
        candidate_preparer=fake_prepare,
        snapshotter=snapshotter,
        flusher=no_flush,
    )
    return operational, prepared, credential


def validate(refresh, prepared, credential):
    return refresh.validate_refresh_candidate(
        prepared,
        credential,
        credential_loader=lambda _info, _scopes: credential,
        snapshotter=snapshotter,
    )


def test_public_refresh_contract_is_available() -> None:
    refresh = load_module()
    assert {
        "refresh_credential_in_memory",
        "prepare_refresh_candidate",
        "validate_refresh_candidate",
        "promote_refresh_candidate_atomically",
        "rollback_refresh_promotion",
    }.issubset(set(refresh.__all__))


def test_successful_promotion_is_atomic_and_preserves_only_candidate_bytes(tmp_path: Path) -> None:
    refresh = load_module()
    operational, prepared, credential = make_prepared(refresh, tmp_path)
    original = operational.read_bytes()
    result = refresh.promote_refresh_candidate_atomically(
        prepared,
        validate(refresh, prepared, credential),
        backup_path=tmp_path / "backup.json",
        candidate_preparer=fake_prepare,
        snapshotter=snapshotter,
        flusher=no_flush,
    )
    assert operational.read_bytes() != original
    assert hashlib.sha256(operational.read_bytes()).hexdigest() == prepared.candidate_hash
    assert result.operational_hash == prepared.candidate_hash
    assert not prepared.candidate.exists()
    assert not (tmp_path / "backup.json").exists()


def test_refresh_endpoint_failure_leaves_operational_token_unchanged(tmp_path: Path) -> None:
    refresh = load_module()
    operational = tmp_path / "google_token.json"
    operational.write_bytes(b"operational-baseline")
    credential = FakeCredential(refresh_error=RuntimeError("synthetic endpoint failure"))
    with pytest.raises(refresh.RefreshPersistenceError) as error:
        refresh.refresh_and_persist_credential(credential, object(), operational, SCOPES)
    assert error.value.code == "REFRESH_FAILED"
    assert credential.refresh_calls == 1
    assert operational.read_bytes() == b"operational-baseline"


@pytest.mark.parametrize(
    ("credential", "code"),
    [
        (FakeCredential(refresh_token=None), "REFRESH_TOKEN_MISSING"),
        (FakeCredential(valid=False), "CREDENTIAL_NOT_VALID"),
        (FakeCredential(scopes=[SCOPES[0]]), "GRANTED_SCOPE_SET_MISMATCH"),
        (FakeCredential(scopes=SCOPES + ["scope:drive"]), "GRANTED_SCOPE_SET_MISMATCH"),
        (FakeCredential(client_id="different-client"), "CLIENT_IDENTITY_MISMATCH"),
    ],
)
def test_candidate_validation_rejects_required_credential_invariants(tmp_path: Path, credential: FakeCredential, code: str) -> None:
    refresh = load_module()
    if code == "REFRESH_TOKEN_MISSING":
        with pytest.raises(refresh.RefreshPersistenceError) as error:
            refresh.refresh_credential_in_memory(credential, object())
        assert error.value.code == code
        return
    _operational, prepared, credential = make_prepared(refresh, tmp_path, credential)
    result = validate(refresh, prepared, credential)
    assert result.accepted is False
    assert result.invariant_code == code


def test_serialization_failure_leaves_operational_token_unchanged(tmp_path: Path) -> None:
    refresh = load_module()
    operational = tmp_path / "google_token.json"
    operational.write_text(json.dumps({"client_id": "expected-client"}))
    credential = FakeCredential(serialization_error=TypeError("synthetic serialization failure"))
    with pytest.raises(refresh.RefreshPersistenceError) as error:
        refresh.prepare_refresh_candidate(
            operational,
            credential,
            SCOPES,
            candidate_path=tmp_path / "candidate.json",
            candidate_preparer=fake_prepare,
            snapshotter=snapshotter,
            flusher=no_flush,
        )
    assert error.value.code == "SERIALIZATION_FAILED"
    assert operational.read_text() == json.dumps({"client_id": "expected-client"})


def test_acl_failure_removes_candidate_and_preserves_operational_token(tmp_path: Path) -> None:
    refresh = load_module()
    operational = tmp_path / "google_token.json"
    operational.write_text(json.dumps({"client_id": "expected-client"}))
    candidate = tmp_path / "candidate.json"
    with pytest.raises(refresh.RefreshPersistenceError) as error:
        refresh.prepare_refresh_candidate(
            operational,
            FakeCredential(),
            SCOPES,
            candidate_path=candidate,
            candidate_preparer=lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("ACL failure")),
            snapshotter=snapshotter,
            flusher=no_flush,
        )
    assert error.value.code == "CANDIDATE_PREPARATION_FAILED"
    assert not candidate.exists()
    assert json.loads(operational.read_text())["client_id"] == "expected-client"


def test_backup_failure_preserves_operational_and_candidate(tmp_path: Path) -> None:
    refresh = load_module()
    operational, prepared, credential = make_prepared(refresh, tmp_path)
    original = operational.read_bytes()
    backup = tmp_path / "backup.json"

    def fail_backup(_reference, destination, data, **_kwargs):
        if Path(destination) == backup:
            raise OSError("synthetic backup failure")
        return fake_prepare(None, destination, data)

    with pytest.raises(refresh.RefreshPersistenceError) as error:
        refresh.promote_refresh_candidate_atomically(
            prepared,
            validate(refresh, prepared, credential),
            backup_path=backup,
            candidate_preparer=fail_backup,
            snapshotter=snapshotter,
            flusher=no_flush,
        )
    assert error.value.code == "BACKUP_FAILED"
    assert operational.read_bytes() == original
    assert prepared.candidate.exists()


def test_atomic_replace_failure_restores_operational_token(tmp_path: Path) -> None:
    refresh = load_module()
    operational, prepared, credential = make_prepared(refresh, tmp_path)
    original = operational.read_bytes()
    backup = tmp_path / "backup.json"

    def fail_candidate_replace(source, destination):
        if Path(source) == prepared.candidate:
            raise OSError("synthetic replace failure")
        os.replace(source, destination)

    with pytest.raises(refresh.RefreshPersistenceError) as error:
        refresh.promote_refresh_candidate_atomically(
            prepared,
            validate(refresh, prepared, credential),
            backup_path=backup,
            candidate_preparer=fake_prepare,
            replacer=fail_candidate_replace,
            snapshotter=snapshotter,
            flusher=no_flush,
        )
    assert error.value.code == "PROMOTION_FAILED"
    assert operational.read_bytes() == original
    assert prepared.candidate.exists()
    assert not backup.exists()


def test_post_replace_validation_failure_rolls_back_exact_original(tmp_path: Path) -> None:
    refresh = load_module()
    operational, prepared, credential = make_prepared(refresh, tmp_path)
    original = operational.read_bytes()
    backup = tmp_path / "backup.json"
    with pytest.raises(refresh.RefreshPersistenceError) as error:
        refresh.promote_refresh_candidate_atomically(
            prepared,
            validate(refresh, prepared, credential),
            backup_path=backup,
            candidate_preparer=fake_prepare,
            snapshotter=snapshotter,
            flusher=no_flush,
            post_replace_validator=lambda _path: (_ for _ in ()).throw(OSError("synthetic validation failure")),
        )
    assert error.value.code == "POST_REPLACE_FAILED"
    assert operational.read_bytes() == original
    assert prepared.candidate.exists()
    assert not backup.exists()


def test_rollback_failure_is_reported_distinctly(tmp_path: Path) -> None:
    refresh = load_module()
    operational, prepared, credential = make_prepared(refresh, tmp_path)
    backup = tmp_path / "backup.json"

    def fail_rollback(source, destination):
        if Path(source) == backup:
            raise OSError("synthetic rollback failure")
        os.replace(source, destination)

    with pytest.raises(refresh.RefreshPersistenceError) as error:
        refresh.promote_refresh_candidate_atomically(
            prepared,
            validate(refresh, prepared, credential),
            backup_path=backup,
            candidate_preparer=fake_prepare,
            replacer=fail_rollback,
            snapshotter=snapshotter,
            flusher=no_flush,
            post_replace_validator=lambda _path: (_ for _ in ()).throw(OSError("trigger rollback")),
        )
    assert error.value.code == "POST_REPLACE_FAILED"
    assert error.value.rollback_code == "ROLLBACK_FAILED"


def test_concurrent_refresh_lock_prevents_any_promotion_mutation(tmp_path: Path) -> None:
    refresh = load_module()
    operational, prepared, credential = make_prepared(refresh, tmp_path)
    original = operational.read_bytes()
    lock = operational.with_name(f".{operational.name}.refresh.lock")
    lock.write_bytes(b"another refresh owns this lock")
    with pytest.raises(refresh.RefreshPersistenceError) as error:
        refresh.promote_refresh_candidate_atomically(
            prepared,
            validate(refresh, prepared, credential),
            backup_path=tmp_path / "backup.json",
            candidate_preparer=fake_prepare,
            snapshotter=snapshotter,
            flusher=no_flush,
        )
    assert error.value.code == "CONCURRENT_REFRESH"
    assert operational.read_bytes() == original
    assert prepared.candidate.exists()


def test_lock_write_failure_removes_stale_lock_and_preserves_operational_token(tmp_path: Path, monkeypatch) -> None:
    refresh = load_module()
    operational, prepared, credential = make_prepared(refresh, tmp_path)
    original = operational.read_bytes()
    lock = operational.with_name(f".{operational.name}.refresh.lock")

    monkeypatch.setattr(refresh.os, "write", lambda *_args: (_ for _ in ()).throw(OSError("synthetic lock write failure")))

    with pytest.raises(refresh.RefreshPersistenceError) as error:
        refresh.promote_refresh_candidate_atomically(
            prepared,
            validate(refresh, prepared, credential),
            backup_path=tmp_path / "backup.json",
            candidate_preparer=fake_prepare,
            snapshotter=snapshotter,
            flusher=no_flush,
        )

    assert error.value.code == "LOCK_FAILED"
    assert operational.read_bytes() == original
    assert prepared.candidate.exists()
    assert not lock.exists()


def test_operational_token_is_unchanged_until_promotion(tmp_path: Path) -> None:
    refresh = load_module()
    operational, prepared, credential = make_prepared(refresh, tmp_path)
    original = operational.read_bytes()
    assert validate(refresh, prepared, credential).accepted is True
    assert operational.read_bytes() == original
    assert prepared.candidate.read_bytes() != original


def test_secret_free_evidence_never_renders_credential_values(tmp_path: Path) -> None:
    refresh = load_module()
    sentinel = "DO-NOT-RENDER-SECRET-SENTINEL"
    credential = FakeCredential(refresh_token=sentinel)
    _operational, prepared, credential = make_prepared(refresh, tmp_path, credential)
    validation = validate(refresh, prepared, credential)
    evidence = json.dumps(refresh.refresh_evidence(prepared, validation), sort_keys=True)
    assert sentinel not in evidence
    assert "synthetic-access-token" not in evidence
    assert "expected-client" not in evidence


def test_integrated_replace_failure_cleans_temporary_candidate_and_lock(tmp_path: Path) -> None:
    refresh = load_module()
    operational = tmp_path / "google_token.json"
    original = json.dumps({"client_id": "expected-client", "refresh_token": "original", "scopes": SCOPES}).encode("utf-8")
    operational.write_bytes(original)
    candidate = tmp_path / "candidate.json"
    backup = tmp_path / "backup.json"

    def fail_candidate_replace(source, destination):
        if Path(source) == candidate:
            raise OSError("synthetic replacement failure")
        os.replace(source, destination)

    with pytest.raises(refresh.RefreshPersistenceError) as error:
        refresh.refresh_and_persist_credential(
            FakeCredential(),
            object(),
            operational,
            SCOPES,
            candidate_path=candidate,
            backup_path=backup,
            candidate_preparer=fake_prepare,
            snapshotter=snapshotter,
            flusher=no_flush,
            credential_loader=lambda _info, _scopes: FakeCredential(),
            replacer=fail_candidate_replace,
        )

    assert error.value.code == "PROMOTION_FAILED"
    assert operational.read_bytes() == original
    assert not candidate.exists()
    assert not backup.exists()
    assert not operational.with_name(f".{operational.name}.refresh.lock").exists()


def test_integrated_refresh_is_in_memory_until_atomic_promotion(tmp_path: Path) -> None:
    refresh = load_module()
    operational = tmp_path / "google_token.json"
    operational.write_text(json.dumps({"client_id": "expected-client", "refresh_token": "original", "scopes": SCOPES}))
    credential = FakeCredential()
    result = refresh.refresh_and_persist_credential(
        credential,
        object(),
        operational,
        SCOPES,
        candidate_path=tmp_path / "candidate.json",
        backup_path=tmp_path / "backup.json",
        candidate_preparer=fake_prepare,
        snapshotter=snapshotter,
        flusher=no_flush,
        credential_loader=lambda _info, _scopes: credential,
    )
    assert result is credential
    assert credential.refresh_calls == 1
    assert json.loads(operational.read_text())["refresh_token"] == "synthetic-refresh-token"
    assert not (tmp_path / "candidate.json").exists()
    assert not (tmp_path / "backup.json").exists()


def _load_script(name: str, filename: str):
    scripts = ROOT / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        spec = importlib.util.spec_from_file_location(name, scripts / filename)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        sys.modules[spec.name] = module
        try:
            spec.loader.exec_module(module)
        finally:
            sys.modules.pop(spec.name, None)
        return module
    finally:
        sys.path.remove(str(scripts))


def test_ops_and_sync_use_durable_refresh_boundary_without_live_calls(tmp_path: Path, monkeypatch) -> None:
    ops = _load_script("refresh_test_ops", "non_profit_hermes_ops.py")
    sync = _load_script("refresh_test_sync", "sync_approved_safe_data.py")
    calls: list[tuple[object, object, Path, list[str]]] = []

    def durable_refresh(credential, request, token, scopes):
        calls.append((credential, request, Path(token), scopes))
        return credential

    for module in (ops, sync):
        credential = FakeCredential(expired=True)
        monkeypatch.setattr(
            module,
            "Credentials",
            type("FakeCredentials", (), {"from_authorized_user_file": staticmethod(lambda *_args, c=credential, **_kwargs: c)}),
        )
        monkeypatch.setattr(module, "Request", lambda: "synthetic-request")
        monkeypatch.setattr(module, "refresh_and_persist_credential", durable_refresh)
        monkeypatch.setattr(module, "TOKEN", tmp_path / f"{module.__name__}.json")

    assert ops.get_creds().refresh_calls == 0
    assert sync.creds(persist_refresh=True).refresh_calls == 0
    assert len(calls) == 2
    assert all(call[2].parent == tmp_path for call in calls)
    assert calls[0][3] == ops.SCOPES
    assert calls[1][3] == sync.SCOPES

    calls.clear()
    assert sync.creds(persist_refresh=False).refresh_calls == 1
    assert calls == []
