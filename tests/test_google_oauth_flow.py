"""Offline fake-only tests for the production OAuth loopback orchestration seam."""
from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
MODULE_PATH = SCRIPTS / "google_oauth_flow.py"


def load_module():
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("google_oauth_flow", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
        sys.path.remove(str(SCRIPTS))
    return module


REDIRECT = "http://127.0.0.1:43127/"
SCOPES = frozenset(
    {
        "scope.calendar.readonly",
        "scope.calendar.events",
        "scope.sheets.readonly",
        "scope.sheets.write",
        "scope.drive.metadata.readonly",
        "scope.drive.file",
        "scope.userinfo.profile",
        "scope.userinfo.email",
    }
)
STATE = "opaque-state-sentinel"
VERIFIER = "opaque-verifier-sentinel"
CODE = "opaque-code-sentinel"


@dataclass
class FakeListener:
    result: dict[str, object]
    redirect_uri: str = REDIRECT
    authorization_code: str | None = CODE
    close_calls: int = 0
    wait_calls: int = 0

    def wait(self, timeout=None):
        del timeout
        self.wait_calls += 1
        return dict(self.result)

    def close(self):
        self.close_calls += 1


class FakeFlow:
    def __init__(self, redirect_uri: str, scopes: frozenset[str], events: list[str]):
        self.authorization_redirect_uri = redirect_uri
        self.exchange_redirect_uri = redirect_uri
        self.scopes = scopes
        self._events = events
        self.authorization_url_calls = 0

    def authorization_url(self):
        self.authorization_url_calls += 1
        self._events.append("authorization_url")
        return "synthetic-url-without-being-returned"


class FakePendingStore:
    def __init__(self, redirect_override=None):
        self.redirect_override = redirect_override
        self.payload = None
        self.save_calls = 0
        self.load_calls = 0
        self.clear_calls = 0
        self.events: list[str] = []
        self.saved_payloads = []

    def save(self, payload):
        self.save_calls += 1
        if self.redirect_override is not None:
            payload = type(payload)(
                redirect_uri=self.redirect_override,
                state=payload.state,
                verifier=payload.verifier,
                expires_at=payload.expires_at,
            )
        self.payload = payload
        self.saved_payloads.append(payload)
        self.events.append("save")

    def load(self):
        self.load_calls += 1
        return self.payload

    def clear(self):
        self.clear_calls += 1
        self.payload = None
        self.events.append("clear")


class FakeExchange:
    def __init__(self):
        self.calls: list[tuple[str, str, str]] = []

    def __call__(self, code: str, redirect_uri: str, verifier: str):
        self.calls.append((code, redirect_uri, verifier))
        return "synthetic-token-never-returned"


def accepted_result(redirect_uri: str = REDIRECT) -> dict[str, object]:
    return {
        "accepted": True,
        "invariant_code": "REDIRECT_ACCEPTED",
        "callback_redirect_uri": redirect_uri,
        "state_matches": True,
    }


def make_run(
    module,
    callback=None,
    *,
    flow_redirect=REDIRECT,
    pending_redirect=None,
    now_values=(100.0, 100.0),
):
    events: list[str] = []
    listener = FakeListener(callback or accepted_result())
    store = FakePendingStore(pending_redirect)
    exchange = FakeExchange()

    def listener_factory(*, state, port, timeout):
        assert state == STATE
        assert port == 0
        del timeout
        events.append("listener_started")
        return listener

    def flow_factory(*, redirect_uri, scopes, state, verifier):
        events.append("flow_factory")
        assert redirect_uri == REDIRECT
        assert state == STATE
        assert verifier == VERIFIER
        return FakeFlow(flow_redirect, scopes, events)

    now_calls = iter(now_values)
    result = module.run_oauth_exchange(
        scopes=SCOPES,
        listener_factory=listener_factory,
        flow_factory=flow_factory,
        pending_store=store,
        exchange=exchange,
        state_factory=lambda: STATE,
        verifier_factory=lambda: VERIFIER,
        now=lambda: next(now_calls),
        timeout=2.0,
    )
    return result, listener, store, exchange, events


def test_success_binds_before_factory_and_reuses_exact_uri_through_one_exchange():
    module = load_module()
    result, listener, store, exchange, events = make_run(module)

    assert result == {"accepted": True, "invariant_code": "EXCHANGE_COMPLETED", "exchange_attempted": True}
    assert events[:2] == ["listener_started", "flow_factory"]
    assert listener.close_calls == 1
    assert listener.wait_calls == 1
    assert store.save_calls == 1
    assert store.clear_calls == 1
    assert store.payload is None
    assert store.saved_payloads[0].redirect_uri == REDIRECT
    assert store.saved_payloads[0].state == STATE
    assert store.saved_payloads[0].verifier == VERIFIER
    assert exchange.calls == [(CODE, REDIRECT, VERIFIER)]
    assert store.events == ["save", "clear"]


def test_exact_immutable_scope_set_is_passed_without_narrowing_or_mutation():
    module = load_module()
    observed = []
    listener = FakeListener(accepted_result())
    store = FakePendingStore()
    exchange = FakeExchange()

    def flow_factory(*, redirect_uri, scopes, state, verifier):
        del redirect_uri, state, verifier
        observed.append(scopes)
        return FakeFlow(REDIRECT, scopes, [])

    result = module.run_oauth_exchange(
        scopes=SCOPES,
        listener_factory=lambda **kwargs: listener,
        flow_factory=flow_factory,
        pending_store=store,
        exchange=exchange,
        state_factory=lambda: STATE,
        verifier_factory=lambda: VERIFIER,
        now=lambda: 100.0,
    )

    assert result["accepted"] is True
    assert observed == [SCOPES]
    assert observed[0] is SCOPES
    assert observed[0] == SCOPES


def test_fixed_port_request_is_rejected_before_any_listener_or_exchange():
    module = load_module()
    calls = []
    result = module.run_oauth_exchange(
        scopes=SCOPES,
        port=43127,
        listener_factory=lambda **kwargs: calls.append(kwargs),
        flow_factory=lambda **kwargs: pytest.fail("flow factory must not run"),
        pending_store=FakePendingStore(),
        exchange=FakeExchange(),
    )

    assert result == {"accepted": False, "invariant_code": "LOOPBACK_BIND_FAILED", "exchange_attempted": False}
    assert calls == []


@pytest.mark.parametrize(
    ("callback", "expected"),
    [
        ({**accepted_result(), "callback_redirect_uri": "http://127.0.0.1:43128/"}, "CALLBACK_REDIRECT_MISMATCH"),
        ({**accepted_result(), "state_matches": False}, "STATE_MISMATCH"),
        ({"accepted": False, "invariant_code": "CALLBACK_OAUTH_ERROR"}, "CALLBACK_OAUTH_ERROR"),
        ({"accepted": False, "invariant_code": "CALLBACK_EXPIRED"}, "CALLBACK_EXPIRED"),
        ({"accepted": False, "invariant_code": "SECOND_CALLBACK_REJECTED"}, "SECOND_CALLBACK_REJECTED"),
    ],
)
def test_callback_rejection_never_exchanges_and_always_consumes_pending(callback, expected):
    module = load_module()
    result, listener, store, exchange, _ = make_run(module, callback)

    assert result == {"accepted": False, "invariant_code": expected, "exchange_attempted": False}
    assert exchange.calls == []
    assert listener.close_calls == 1
    assert store.clear_calls == 1
    assert store.payload is None


def test_pending_redirect_mismatch_blocks_exchange_without_secret_diagnostics():
    module = load_module()
    sentinel = VERIFIER
    result, listener, store, exchange, _ = make_run(
        module,
        pending_redirect="http://127.0.0.1:43128/",
    )

    assert result == {
        "accepted": False,
        "invariant_code": "PENDING_REDIRECT_MISMATCH",
        "exchange_attempted": False,
    }
    assert exchange.calls == []
    assert listener.close_calls == 1
    assert store.clear_calls == 1
    assert sentinel not in repr(result)


def test_authorization_and_exchange_redirect_mismatch_blocks_exchange():
    module = load_module()
    result, listener, store, exchange, events = make_run(module, flow_redirect="http://127.0.0.1:43128/")

    assert result == {
        "accepted": False,
        "invariant_code": "AUTH_EXCHANGE_REDIRECT_MISMATCH",
        "exchange_attempted": False,
    }
    assert exchange.calls == []
    assert listener.close_calls == 1
    assert store.clear_calls == 1
    assert events[:2] == ["listener_started", "flow_factory"]


def test_flow_factory_error_is_redacted_and_cleans_up_listener_and_pending():
    module = load_module()
    listener = FakeListener(accepted_result())
    store = FakePendingStore()
    exchange = FakeExchange()

    def fail_factory(**kwargs):
        del kwargs
        raise RuntimeError(f"provider leaked {STATE} {VERIFIER}")

    result = module.run_oauth_exchange(
        scopes=SCOPES,
        listener_factory=lambda **kwargs: listener,
        flow_factory=fail_factory,
        pending_store=store,
        exchange=exchange,
        state_factory=lambda: STATE,
        verifier_factory=lambda: VERIFIER,
    )

    assert result == {"accepted": False, "invariant_code": "AUTHORIZATION_CONSTRUCTION_FAILED", "exchange_attempted": False}
    assert listener.close_calls == 1
    assert store.clear_calls == 0
    assert exchange.calls == []
    assert STATE not in repr(result)
    assert VERIFIER not in repr(result)


def test_expired_pending_session_blocks_exchange_and_clears_state():
    module = load_module()
    result, listener, store, exchange, _ = make_run(module, now_values=(100.0, 1000.0))

    assert result == {
        "accepted": False,
        "invariant_code": "PENDING_SESSION_EXPIRED",
        "exchange_attempted": False,
    }
    assert exchange.calls == []
    assert listener.close_calls == 1
    assert store.clear_calls == 1
