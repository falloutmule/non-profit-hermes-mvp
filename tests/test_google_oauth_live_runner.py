"""Offline fake-only tests for the guarded one-shot OAuth runner."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "google_oauth_live_runner.py"


def load_module():
    spec = importlib.util.spec_from_file_location("google_oauth_live_runner", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


STATE = "synthetic-state-never-output"
VERIFIER = "synthetic-verifier-never-output"
CODE = "synthetic-code-never-output"
URL = "https://accounts.google.example/authorize?state=secret-state&code_challenge=secret-verifier"
REDIRECT = "http://127.0.0.1:43127/"


@dataclass
class FakeListener:
    result: dict[str, object]
    redirect_uri: str = REDIRECT
    authorization_code: str = CODE
    close_calls: int = 0

    def wait(self, timeout=None):
        del timeout
        return dict(self.result)

    def close(self):
        self.close_calls += 1


class FakeRawFlow:
    def __init__(self, credentials, *, fetch_error=None, redirect_uri=REDIRECT):
        self.credentials = credentials
        self.fetch_error = fetch_error
        self.fetch_calls = []
        self.redirect_uri = redirect_uri

    def authorization_url(self, **kwargs):
        self.authorization_kwargs = kwargs
        return URL, STATE

    def fetch_token(self, **kwargs):
        self.fetch_calls.append(kwargs)
        if self.fetch_error is not None:
            raise self.fetch_error


class FakeCredentials:
    granted_scopes = None

    def to_json(self):
        return json.dumps(
            {
                "client_id": "client-id-secret-value",
                "client_secret": "client-secret-value",
                "refresh_token": "refresh-token-secret-value",
                "token": "access-token-secret-value",
                "token_uri": "https://oauth2.googleapis.example/token",
            }
        )


def accepted_result(scopes):
    return {
        "accepted": True,
        "invariant_code": "REDIRECT_ACCEPTED",
        "callback_redirect_uri": REDIRECT,
        "state_matches": True,
        "granted_scopes": scopes,
    }


def make_paths(module, tmp_path: Path):
    operational = tmp_path / "google_token.json"
    operational.write_bytes(b"operational-baseline")
    return module.RunnerPaths(
        operational_token=operational,
        client_secret=tmp_path / "google_client_secret.json",
        pending=tmp_path / "google_oauth_pending.json",
        candidate=tmp_path / "google_token.candidate.json",
        url_handoff=tmp_path / "google_oauth_url_handoff.json",
        evidence=tmp_path / "GR_OAUTH_001_URL_EVIDENCE.json",
    )


def fake_prepare(reference, candidate, data, **kwargs):
    del reference, kwargs
    Path(candidate).write_bytes(data)
    return Path(candidate)


def test_runner_imports_exact_active_helper_scopes_and_paths():
    module = load_module()
    helper_dir = Path(module.CLIENT_SECRET_PATH).parent
    sys.path.insert(0, str(helper_dir))
    try:
        import google_api
    finally:
        sys.path.remove(str(helper_dir))
    assert module.SCOPES is google_api.SCOPES
    assert module.TOKEN_PATH is google_api.TOKEN_PATH
    assert module.CLIENT_SECRET_PATH is google_api.CLIENT_SECRET_PATH
    assert tuple(module.SCOPES) == tuple(google_api.SCOPES)


def test_pending_store_serializes_only_restricted_session_and_uses_acl_preparer(tmp_path: Path):
    module = load_module()
    reference = tmp_path / "operational.json"
    reference.write_bytes(b"reference")
    pending = tmp_path / "pending.json"
    calls = []

    def prepare(reference_path, candidate_path, data, **kwargs):
        calls.append((Path(reference_path), Path(candidate_path), data, kwargs))
        Path(candidate_path).write_bytes(data)
        return Path(candidate_path)

    store = module.FilePendingSessionStore(pending, reference, preparer=prepare)
    payload = module.PendingOAuthSession(REDIRECT, STATE, VERIFIER, 123.0)
    store.save(payload)

    assert calls and calls[0][0] == reference and calls[0][1] == pending
    assert json.loads(pending.read_text()) == {
        "redirect_uri": REDIRECT,
        "state": STATE,
        "verifier": VERIFIER,
        "expires_at": 123.0,
    }
    assert store.load() == payload
    store.clear()
    assert not pending.exists()


def test_url_handoff_is_one_shot_and_never_written_before_publish(tmp_path: Path):
    module = load_module()
    reference = tmp_path / "operational.json"
    reference.write_bytes(b"reference")
    handoff_path = tmp_path / "handoff.json"
    calls = []

    def prepare(reference_path, candidate_path, data, **kwargs):
        calls.append((Path(reference_path), Path(candidate_path), data, kwargs))
        Path(candidate_path).write_bytes(data)
        return Path(candidate_path)

    handoff = module.TransientUrlHandoff(handoff_path, reference, preparer=prepare)
    assert not handoff_path.exists()
    handoff.publish(URL)
    assert handoff_path.read_text() == URL
    with pytest.raises(module.RunnerInvariantError):
        handoff.publish(URL)
    assert len(calls) == 1
    handoff.clear()
    assert not handoff_path.exists()


def test_preflight_rejects_existing_candidate_without_listener_or_mutation(tmp_path: Path):
    module = load_module()
    paths = make_paths(module, tmp_path)
    paths.client_secret.write_text(json.dumps({"installed": {"client_id": "client-id"}}))
    paths.candidate.write_bytes(b"stale-candidate")
    listener_calls = []

    result = module.run_guarded_oauth(
        paths,
        listener_factory=lambda **kwargs: listener_calls.append(kwargs),
        flow_factory=lambda **kwargs: pytest.fail("flow must not run"),
        candidate_preparer=fake_prepare,
        now=lambda: 100.0,
        state_factory=lambda: STATE,
        verifier_factory=lambda: VERIFIER,
    )

    assert result["invariant_code"] == "CANDIDATE_PRESENT"
    assert result["exchange_attempted"] is False
    assert listener_calls == []
    assert paths.candidate.read_bytes() == b"stale-candidate"
    assert paths.operational_token.read_bytes() == b"operational-baseline"


def test_success_saves_pending_then_handoff_after_live_listener_and_fetches_once(tmp_path: Path):
    module = load_module()
    paths = make_paths(module, tmp_path)
    paths.client_secret.write_text(json.dumps({"installed": {"client_id": "client-id"}}))
    events = []
    adapters = []
    raw_flow = FakeRawFlow(FakeCredentials())

    def listener_factory(**kwargs):
        del kwargs
        events.append("listener_bound")
        return FakeListener(accepted_result(frozenset(paths.scopes)))

    def preparer(reference, candidate, data, **kwargs):
        events.append("restricted_write")
        return fake_prepare(reference, candidate, data, **kwargs)

    def flow_factory(*, redirect_uri, scopes, state, verifier, handoff):
        del scopes, state, verifier
        assert paths.pending.exists()
        events.append("flow_constructed")
        adapter = module.GoogleAuthFlowAdapter(
            raw_flow,
            redirect_uri=redirect_uri,
            handoff=handoff,
            operational_token=paths.operational_token,
            candidate=paths.candidate,
            baseline_hash=hashlib.sha256(paths.operational_token.read_bytes()).hexdigest(),
            candidate_preparer=preparer,
        )
        adapters.append(adapter)
        return adapter

    result = module.run_guarded_oauth(
        paths,
        listener_factory=listener_factory,
        flow_factory=flow_factory,
        candidate_preparer=preparer,
        now=lambda: 100.0,
        state_factory=lambda: STATE,
        verifier_factory=lambda: VERIFIER,
    )

    assert result["accepted"] is True
    assert result["invariant_code"] == "EXCHANGE_COMPLETED"
    assert adapters[0].authorization_redirect_uri == REDIRECT
    assert adapters[0].exchange_redirect_uri == REDIRECT
    assert events[:3] == ["listener_bound", "restricted_write", "flow_constructed"]
    assert "restricted_write" in events[3:]
    assert raw_flow.fetch_calls == [{"code": CODE}]
    assert paths.operational_token.read_bytes() == b"operational-baseline"
    assert not paths.pending.exists()
    assert not paths.url_handoff.exists()
    assert paths.candidate.exists()
    assert paths.evidence.exists()
    evidence = paths.evidence.read_text()
    assert "secret-state" not in evidence
    assert "secret-verifier" not in evidence
    assert "client-secret-value" not in evidence
    assert "redirect_uri" in evidence


def test_from_client_secret_binds_real_google_flow_redirect_and_publishes_url(tmp_path: Path):
    module = load_module()
    client_secret = tmp_path / "client_secret.json"
    client_secret.write_text(
        json.dumps(
            {
                "installed": {
                    "client_id": "synthetic.apps.googleusercontent.com",
                    "client_secret": "synthetic-secret",
                    "auth_uri": "https://accounts.google.example/auth",
                    "token_uri": "https://oauth2.googleapis.example/token",
                    "redirect_uris": [REDIRECT],
                }
            }
        )
    )
    operational = tmp_path / "operational.json"
    operational.write_bytes(b"operational-baseline")
    handoff = module.TransientUrlHandoff(
        tmp_path / "handoff.json",
        operational,
        preparer=fake_prepare,
    )

    adapter = module.GoogleAuthFlowAdapter.from_client_secret(
        client_secret=client_secret,
        scopes=["scope:a"],
        redirect_uri=REDIRECT,
        state=STATE,
        verifier=VERIFIER,
        handoff=handoff,
        operational_token=operational,
        candidate=tmp_path / "candidate.json",
        baseline_hash=hashlib.sha256(operational.read_bytes()).hexdigest(),
        candidate_preparer=fake_prepare,
    )

    assert adapter.authorization_redirect_uri == REDIRECT
    assert adapter.exchange_redirect_uri == REDIRECT
    assert adapter._flow.redirect_uri == REDIRECT
    assert not hasattr(adapter._flow, "authorization_redirect_uri")
    assert not hasattr(adapter._flow, "exchange_redirect_uri")
    url = adapter.authorization_url()
    assert url.startswith("https://accounts.google.example/")
    assert handoff.path.read_text() == url


def test_adapter_rejects_raw_flow_redirect_mismatch_before_authorization_or_fetch(tmp_path: Path):
    module = load_module()
    operational = tmp_path / "operational.json"
    operational.write_bytes(b"operational-baseline")
    raw_flow = FakeRawFlow(FakeCredentials(), redirect_uri="http://127.0.0.1:43128/")
    handoff = module.TransientUrlHandoff(
        tmp_path / "handoff.json",
        operational,
        preparer=fake_prepare,
    )

    with pytest.raises(module.RunnerInvariantError) as error:
        module.GoogleAuthFlowAdapter(
            raw_flow,
            redirect_uri=REDIRECT,
            handoff=handoff,
            operational_token=operational,
            candidate=tmp_path / "candidate.json",
            baseline_hash=hashlib.sha256(operational.read_bytes()).hexdigest(),
            candidate_preparer=fake_prepare,
        )

    assert error.value.code == "AUTH_EXCHANGE_REDIRECT_MISMATCH"
    assert raw_flow.fetch_calls == []
    assert not handoff.path.exists()


def test_adapter_rejects_missing_raw_flow_redirect_before_authorization_or_fetch(tmp_path: Path):
    module = load_module()
    operational = tmp_path / "operational.json"
    operational.write_bytes(b"operational-baseline")
    raw_flow = FakeRawFlow(FakeCredentials())
    del raw_flow.redirect_uri
    handoff = module.TransientUrlHandoff(
        tmp_path / "handoff.json",
        operational,
        preparer=fake_prepare,
    )

    with pytest.raises(module.RunnerInvariantError) as error:
        module.GoogleAuthFlowAdapter(
            raw_flow,
            redirect_uri=REDIRECT,
            handoff=handoff,
            operational_token=operational,
            candidate=tmp_path / "candidate.json",
            baseline_hash=hashlib.sha256(operational.read_bytes()).hexdigest(),
            candidate_preparer=fake_prepare,
        )

    assert error.value.code == "REDIRECT_URI_MISSING"
    assert raw_flow.fetch_calls == []
    assert not handoff.path.exists()


def test_fetch_failure_is_one_shot_redacted_and_cleans_candidate_pending_handoff(tmp_path: Path):
    module = load_module()
    paths = make_paths(module, tmp_path)
    paths.client_secret.write_text(json.dumps({"installed": {"client_id": "client-id"}}))
    raw_flow = FakeRawFlow(FakeCredentials(), fetch_error=RuntimeError(f"leaked {CODE} {VERIFIER}"))

    def flow_factory(*, redirect_uri, scopes, state, verifier, handoff):
        del scopes, state, verifier
        return module.GoogleAuthFlowAdapter(
            raw_flow,
            redirect_uri=redirect_uri,
            handoff=handoff,
            operational_token=paths.operational_token,
            candidate=paths.candidate,
            baseline_hash=hashlib.sha256(paths.operational_token.read_bytes()).hexdigest(),
            candidate_preparer=fake_prepare,
        )

    result = module.run_guarded_oauth(
        paths,
        listener_factory=lambda **kwargs: FakeListener(accepted_result(frozenset(paths.scopes))),
        flow_factory=flow_factory,
        candidate_preparer=fake_prepare,
        now=lambda: 100.0,
        state_factory=lambda: STATE,
        verifier_factory=lambda: VERIFIER,
    )

    assert result["accepted"] is False
    assert result["invariant_code"] == "EXCHANGE_FAILED"
    assert raw_flow.fetch_calls == [{"code": CODE}]
    assert CODE not in repr(result)
    assert VERIFIER not in repr(result)
    assert not paths.candidate.exists()
    assert not paths.pending.exists()
    assert not paths.url_handoff.exists()
    assert paths.operational_token.read_bytes() == b"operational-baseline"


def test_operational_hash_change_blocks_candidate_write(tmp_path: Path):
    module = load_module()
    paths = make_paths(module, tmp_path)
    paths.client_secret.write_text(json.dumps({"installed": {"client_id": "client-id"}}))
    raw_flow = FakeRawFlow(FakeCredentials())
    prepare_calls = []

    original_fetch = raw_flow.fetch_token

    def mutate_after_endpoint(**kwargs):
        original_fetch(**kwargs)
        paths.operational_token.write_bytes(b"tampered")

    raw_flow.fetch_token = mutate_after_endpoint

    def flow_factory(*, redirect_uri, scopes, state, verifier, handoff):
        del scopes, state, verifier
        return module.GoogleAuthFlowAdapter(
            raw_flow,
            redirect_uri=redirect_uri,
            handoff=handoff,
            operational_token=paths.operational_token,
            candidate=paths.candidate,
            baseline_hash=hashlib.sha256(paths.operational_token.read_bytes()).hexdigest(),
            candidate_preparer=lambda *args, **kwargs: prepare_calls.append((args, kwargs)),
        )

    result = module.run_guarded_oauth(
        paths,
        listener_factory=lambda **kwargs: FakeListener(accepted_result(frozenset(paths.scopes))),
        flow_factory=flow_factory,
        candidate_preparer=fake_prepare,
        now=lambda: 100.0,
        state_factory=lambda: STATE,
        verifier_factory=lambda: VERIFIER,
    )

    assert result["accepted"] is False
    assert result["invariant_code"] in {"EXCHANGE_FAILED", "OPERATIONAL_TOKEN_CHANGED"}
    assert prepare_calls == []
    assert not paths.candidate.exists()


def test_final_result_and_evidence_never_render_secret_values(tmp_path: Path):
    module = load_module()
    paths = make_paths(module, tmp_path)
    paths.client_secret.write_text(
        json.dumps({"installed": {"client_id": "client-id", "client_secret": "client-secret-value"}})
    )
    raw_flow = FakeRawFlow(FakeCredentials(), fetch_error=RuntimeError("secret failure"))

    def flow_factory(*, redirect_uri, scopes, state, verifier, handoff):
        del scopes, state, verifier
        return module.GoogleAuthFlowAdapter(
            raw_flow,
            redirect_uri=redirect_uri,
            handoff=handoff,
            operational_token=paths.operational_token,
            candidate=paths.candidate,
            baseline_hash=hashlib.sha256(paths.operational_token.read_bytes()).hexdigest(),
            candidate_preparer=fake_prepare,
        )

    result = module.run_guarded_oauth(
        paths,
        listener_factory=lambda **kwargs: FakeListener(accepted_result(frozenset(paths.scopes))),
        flow_factory=flow_factory,
        candidate_preparer=fake_prepare,
        now=lambda: 100.0,
        state_factory=lambda: STATE,
        verifier_factory=lambda: VERIFIER,
    )

    rendered = repr(result) + paths.evidence.read_text()
    for secret in (STATE, VERIFIER, CODE, "client-secret-value", "refresh-token-secret-value", "access-token-secret-value"):
        assert secret not in rendered


def test_cli_help_exits_zero_without_dispatch_or_transient_files(tmp_path: Path, capsys):
    module = load_module()
    paths = make_paths(module, tmp_path)
    dispatched = []

    with pytest.raises(SystemExit) as exit_info:
        module.main(
            ["--help"],
            runner=lambda **kwargs: dispatched.append(kwargs),
            paths=paths,
        )

    assert exit_info.value.code == 0
    assert dispatched == []
    assert "execute-live" in capsys.readouterr().out
    assert not paths.pending.exists()
    assert not paths.candidate.exists()
    assert not paths.url_handoff.exists()
    assert not paths.evidence.exists()


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["--unknown"],
        ["--timeout", "not-a-number"],
        ["--dry-run"],
        ["--status"],
    ],
)
def test_non_live_cli_paths_fail_closed_without_dispatch_or_transient_files(tmp_path: Path, capsys, argv):
    module = load_module()
    paths = make_paths(module, tmp_path)
    dispatched = []

    exit_code = module.main(argv, runner=lambda **kwargs: dispatched.append(kwargs), paths=paths)

    rendered = capsys.readouterr().out
    assert exit_code == 1
    assert dispatched == []
    assert "authorization" not in rendered.lower()
    assert not paths.pending.exists()
    assert not paths.candidate.exists()
    assert not paths.url_handoff.exists()
    assert not paths.evidence.exists()


def test_cli_live_arming_requires_matching_baseline_hash_before_dispatch(tmp_path: Path, capsys):
    module = load_module()
    paths = make_paths(module, tmp_path)
    paths.client_secret.write_text(json.dumps({"installed": {"client_id": "client-id"}}))
    dispatched = []

    exit_code = module.main(
        ["--execute-live", "--expected-operational-sha256", "0" * 64],
        runner=lambda **kwargs: dispatched.append(kwargs),
        paths=paths,
    )

    assert exit_code == 1
    assert dispatched == []
    assert json.loads(capsys.readouterr().out)["invariant_code"] == "OPERATIONAL_TOKEN_HASH_MISMATCH"
    assert not paths.pending.exists()
    assert not paths.candidate.exists()
    assert not paths.url_handoff.exists()
    assert not paths.evidence.exists()


def test_cli_dispatches_once_only_after_arming_validated_parameters(tmp_path: Path, capsys):
    module = load_module()
    paths = make_paths(module, tmp_path)
    paths.client_secret.write_text(json.dumps({"installed": {"client_id": "client-id"}}))
    expected_hash = hashlib.sha256(paths.operational_token.read_bytes()).hexdigest()
    dispatched = []

    def runner(**kwargs):
        dispatched.append(kwargs)
        return {"accepted": False, "invariant_code": "CALLBACK_EXPIRED", "exchange_attempted": False}

    exit_code = module.main(
        [
            "--execute-live",
            "--expected-operational-sha256",
            expected_hash,
            "--timeout",
            "45",
            "--pending-ttl",
            "300",
        ],
        runner=runner,
        paths=paths,
    )

    assert exit_code == 1
    assert len(dispatched) == 1
    assert dispatched[0]["paths"] == paths
    assert dispatched[0]["timeout"] == 45.0
    assert dispatched[0]["pending_ttl"] == 300.0
    assert json.loads(capsys.readouterr().out)["invariant_code"] == "CALLBACK_EXPIRED"


def test_default_evidence_is_temp_and_stale_evidence_requires_fresh_temp_output(tmp_path: Path, capsys):
    module = load_module()
    temp_root = Path(tempfile.gettempdir()).resolve()
    assert module.DEFAULT_EVIDENCE_PATH.resolve().is_relative_to(temp_root)
    assert not module.DEFAULT_EVIDENCE_PATH.resolve().is_relative_to(ROOT.resolve())

    paths = make_paths(module, tmp_path)
    paths.client_secret.write_text(json.dumps({"installed": {"client_id": "client-id"}}))
    paths.evidence.write_text("stale")
    expected_hash = hashlib.sha256(paths.operational_token.read_bytes()).hexdigest()
    dispatched = []

    blocked = module.main(
        ["--execute-live", "--expected-operational-sha256", expected_hash],
        runner=lambda **kwargs: dispatched.append(kwargs),
        paths=paths,
    )

    assert blocked == 1
    assert dispatched == []
    assert json.loads(capsys.readouterr().out)["invariant_code"] == "EVIDENCE_PRESENT"

    fresh = temp_root / "GR_OAUTH_001_fresh_evidence.json"
    if fresh.exists():
        fresh.unlink()
    dispatched_result = module.main(
        [
            "--execute-live",
            "--expected-operational-sha256",
            expected_hash,
            "--fresh-output",
            str(fresh),
        ],
        runner=lambda **kwargs: dispatched.append(kwargs) or {"accepted": False, "invariant_code": "CALLBACK_EXPIRED"},
        paths=paths,
    )

    assert dispatched_result == 1
    assert len(dispatched) == 1
    assert dispatched[0]["paths"].evidence == fresh
