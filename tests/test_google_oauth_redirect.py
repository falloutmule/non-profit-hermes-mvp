"""Offline tests for the installed-app loopback redirect contract and listener."""
from __future__ import annotations

import importlib.util
import socket
import sys
import threading
import time
from dataclasses import FrozenInstanceError
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "google_oauth_redirect.py"


def load_module():
    spec = importlib.util.spec_from_file_location("google_oauth_redirect", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


def test_resolve_returns_a_live_bound_listener_with_its_exact_redirect() -> None:
    module = load_module()
    bound = module.resolve_installed_redirect()
    try:
        assert bound.redirect_uri.startswith("http://127.0.0.1:")
        assert bound.redirect_uri.endswith("/")
        assert int(bound.redirect_uri.rsplit(":", 1)[1][:-1]) > 0
        assert bound.socket is not None
        with socket.create_connection(("127.0.0.1", bound.port), timeout=1):
            pass
    finally:
        bound.close()
    assert bound.socket is None


def test_resolve_rejects_non_loopback_host() -> None:
    module = load_module()
    for host in ("localhost", "0.0.0.0", "192.0.2.1", "::1"):
        with pytest.raises(module.RedirectContractError) as error:
            module.resolve_installed_redirect(host, 0)
        assert error.value.code == "LOOPBACK_BIND_FAILED"


@pytest.mark.parametrize("port", [True, False, "0", None, -1, 1, 43127, 65536])
def test_public_entry_points_reject_every_port_request_except_integer_zero(port) -> None:
    module = load_module()
    with pytest.raises(module.RedirectContractError) as error:
        module.resolve_installed_redirect("127.0.0.1", port)
    assert error.value.code == "LOOPBACK_BIND_FAILED"

    with pytest.raises(module.RedirectContractError) as error:
        module.start_one_shot_callback_listener(state="synthetic", port=port, timeout=1)
    assert error.value.code == "LOOPBACK_BIND_FAILED"


def test_listener_uses_live_bound_result_without_a_closed_probe_uri(monkeypatch) -> None:
    module = load_module()
    bound = module.resolve_installed_redirect()
    try:
        def closed_probe_must_not_be_used(*args, **kwargs):
            del args, kwargs
            raise AssertionError("closed port probe must not produce a listener URI")

        monkeypatch.setattr(module, "resolve_installed_redirect", closed_probe_must_not_be_used)
        listener = module.start_one_shot_callback_listener(
            bound,
            state="synthetic",
            timeout=2.0,
        )
        try:
            assert listener.redirect_uri == bound.redirect_uri
            assert listener.socket is not None
            with socket.create_connection(("127.0.0.1", listener.port), timeout=1):
                pass
        finally:
            listener.close()
        assert not listener.thread.is_alive()
        assert listener.socket is None
    finally:
        bound.close()


def test_bound_redirect_uri_is_immutable_until_listener_ownership_transfers() -> None:
    module = load_module()
    bound = module.resolve_installed_redirect()
    try:
        with pytest.raises(FrozenInstanceError):
            bound.redirect_uri = "http://127.0.0.1:43127/"
    finally:
        bound.close()


def test_listener_start_failure_closes_the_claimed_live_socket(monkeypatch) -> None:
    module = load_module()
    bound = module.resolve_installed_redirect()
    server = bound._server
    assert server is not None

    def fail_start(listener) -> None:
        del listener
        raise RuntimeError("synthetic start failure")

    monkeypatch.setattr(module.OneShotCallbackListener, "start", fail_start)
    with pytest.raises(RuntimeError, match="synthetic start failure"):
        module.start_one_shot_callback_listener(bound, state="synthetic", timeout=1)
    assert server.socket is None
    assert not any(thread.name.startswith("google-oauth-loopback-") for thread in threading.enumerate())


def test_contract_accepts_one_exact_redirect_for_authorization_exchange_and_callback() -> None:
    module = load_module()
    redirect = "http://127.0.0.1:43127/"
    result = module.validate_redirect_contract(
        redirect,
        redirect,
        redirect,
        redirect,
    )
    assert result == {"accepted": True, "invariant_code": "REDIRECT_ACCEPTED"}


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"client_type": "web"}, "CLIENT_TYPE_NOT_INSTALLED"),
        ({"redirect_uri": None}, "REDIRECT_URI_MISSING"),
        (
            {"authorization_redirect_uri": "http://127.0.0.1:43128/"},
            "AUTH_EXCHANGE_REDIRECT_MISMATCH",
        ),
        (
            {"exchange_redirect_uri": "http://127.0.0.1:43128/"},
            "AUTH_EXCHANGE_REDIRECT_MISMATCH",
        ),
        (
            {"callback_redirect_uri": "http://127.0.0.1:43128/"},
            "CALLBACK_REDIRECT_MISMATCH",
        ),
    ],
)
def test_contract_returns_stable_failure_codes(kwargs, expected) -> None:
    module = load_module()
    redirect = "http://127.0.0.1:43127/"
    values = {
        "redirect_uri": redirect,
        "authorization_redirect_uri": redirect,
        "exchange_redirect_uri": redirect,
        "callback_redirect_uri": redirect,
    }
    values.update(kwargs)
    result = module.validate_redirect_contract(**values)
    assert result["accepted"] is False
    assert result["invariant_code"] == expected


@pytest.mark.parametrize(
    "redirect",
    [
        "http://localhost:1/",
        "http://127.0.0.1:43127",
        "http://127.0.0.1:43127/callback",
        "https://127.0.0.1:43127/",
        "http://user:pass@127.0.0.1:43127/",
        "http://127.0.0.1:43127/#fragment",
        "http://0.0.0.0:43127/",
    ],
)
def test_contract_rejects_unsafe_or_noncanonical_uri(redirect) -> None:
    module = load_module()
    result = module.validate_redirect_contract(
        redirect,
        redirect,
        redirect,
        redirect,
    )
    assert result["accepted"] is False
    assert result["invariant_code"] == "REDIRECT_URI_MISSING"


def test_listener_is_active_before_consumer_use_and_accepts_one_root_callback() -> None:
    module = load_module()
    listener = module.start_one_shot_callback_listener(
        state="synthetic-state",
        timeout=2.0,
    )
    try:
        assert listener.redirect_uri.startswith("http://127.0.0.1:")
        with socket.create_connection(("127.0.0.1", listener.port), timeout=1):
            pass
        with urlopen(
            listener.redirect_uri + "?state=synthetic-state&code=synthetic-code",
            timeout=1,
        ) as response:
            body = response.read().decode("utf-8")
            assert response.status == 200
        result = listener.wait(timeout=2)
        assert result["accepted"] is True
        assert result["invariant_code"] == "REDIRECT_ACCEPTED"
        assert result["callback_redirect_uri"] == listener.redirect_uri
        assert result["state_matches"] is True
        assert "synthetic-code" not in body
    finally:
        listener.close()
    assert not listener.thread.is_alive()
    assert listener.socket is None


def test_listener_rejects_state_mismatch() -> None:
    module = load_module()
    listener = module.start_one_shot_callback_listener(state="expected", timeout=2.0)
    try:
        with pytest.raises(HTTPError) as error:
            urlopen(listener.redirect_uri + "?state=wrong&code=synthetic", timeout=1)
        assert error.value.code == 400
        result = listener.wait(timeout=2)
        assert result["invariant_code"] == "STATE_MISMATCH"
    finally:
        listener.close()


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("state=synthetic", "CALLBACK_MISSING_CODE"),
        ("state=synthetic&error=access_denied", "CALLBACK_OAUTH_ERROR"),
    ],
)
def test_listener_rejects_missing_code_and_oauth_error(query, expected) -> None:
    module = load_module()
    listener = module.start_one_shot_callback_listener(state="synthetic", timeout=2.0)
    try:
        with pytest.raises(HTTPError) as error:
            urlopen(listener.redirect_uri + "?" + query, timeout=1)
        assert error.value.code == 400
        assert listener.wait(timeout=2)["invariant_code"] == expected
    finally:
        listener.close()


def test_listener_rejects_wrong_path_and_trailing_redirect_mismatch() -> None:
    module = load_module()
    listener = module.start_one_shot_callback_listener(state="synthetic", timeout=2.0)
    try:
        with pytest.raises(HTTPError) as error:
            urlopen(
                listener.redirect_uri.rstrip("/") + "/wrong"
                + "?state=synthetic&code=synthetic",
                timeout=1,
            )
        assert error.value.code == 400
        assert listener.wait(timeout=2)["invariant_code"] == "CALLBACK_REDIRECT_MISMATCH"
    finally:
        listener.close()


def test_consume_callback_once_rejects_second_callback() -> None:
    module = load_module()
    listener = module.start_one_shot_callback_listener(state="synthetic", timeout=2.0)
    try:
        first = module.consume_callback_once(
            listener,
            listener.redirect_uri + "?state=synthetic&code=first",
        )
        second = module.consume_callback_once(
            listener,
            listener.redirect_uri + "?state=synthetic&code=second",
        )
        assert first["invariant_code"] == "REDIRECT_ACCEPTED"
        assert second["invariant_code"] == "SECOND_CALLBACK_REJECTED"
    finally:
        listener.close()
    assert not listener.thread.is_alive()


def test_listener_expires_and_cleans_up() -> None:
    module = load_module()
    listener = module.start_one_shot_callback_listener(state="synthetic", timeout=0.02)
    result = listener.wait(timeout=2)
    assert result["invariant_code"] == "CALLBACK_EXPIRED"
    listener.close()
    assert not listener.thread.is_alive()
    assert listener.socket is None
    assert not any(
        thread.is_alive() and thread.name == listener.thread.name
        for thread in threading.enumerate()
    )


def test_listener_cleanup_is_idempotent() -> None:
    module = load_module()
    listener = module.start_one_shot_callback_listener(state="synthetic", timeout=2.0)
    listener.close()
    listener.close()
    assert not listener.thread.is_alive()
    assert listener.socket is None
    time.sleep(0.01)


@pytest.mark.parametrize(
    ("query", "expected_code", "expected_comparison"),
    [
        ("state=expected&code=synthetic", "REDIRECT_ACCEPTED", ("expected", "expected")),
        ("state=wrong&code=synthetic", "STATE_MISMATCH", ("wrong", "expected")),
    ],
)
def test_callback_state_uses_constant_time_comparison_for_equal_and_unequal_values(
    monkeypatch,
    query,
    expected_code,
    expected_comparison,
) -> None:
    module = load_module()
    assert hasattr(module, "hmac")
    compare_digest = module.hmac.compare_digest
    calls = []

    def observe_compare_digest(left, right):
        calls.append((left, right))
        return compare_digest(left, right)

    monkeypatch.setattr(module.hmac, "compare_digest", observe_compare_digest)
    listener = module.start_one_shot_callback_listener(state="expected", timeout=2.0)
    try:
        result = listener._consume_query(query)
        assert result["invariant_code"] == expected_code
        assert expected_comparison in calls
    finally:
        listener.close()
    assert listener.socket is None


def test_callback_rejects_malformed_non_string_state_before_constant_time_comparison(
    monkeypatch,
) -> None:
    module = load_module()
    assert hasattr(module, "hmac")
    calls = []

    def observe_compare_digest(left, right):
        calls.append((left, right))
        return True

    monkeypatch.setattr(module.hmac, "compare_digest", observe_compare_digest)
    monkeypatch.setattr(module, "parse_qs", lambda *args, **kwargs: {"state": [object()]})
    listener = module.start_one_shot_callback_listener(state="expected", timeout=2.0)
    try:
        result = listener._consume_query("state=ignored&code=synthetic")
        assert result["invariant_code"] == "STATE_MISMATCH"
        assert calls == []
    finally:
        listener.close()
    assert listener.socket is None
