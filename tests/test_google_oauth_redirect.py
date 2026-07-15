"""Offline tests for the installed-app loopback redirect contract and listener."""
from __future__ import annotations

import importlib.util
import socket
import sys
import threading
import time
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


def test_resolve_uses_ipv4_loopback_and_random_port() -> None:
    redirect = load_module().resolve_installed_redirect()
    assert redirect.startswith("http://127.0.0.1:")
    assert redirect.endswith("/")
    assert int(redirect.rsplit(":", 1)[1][:-1]) > 0


def test_resolve_rejects_non_loopback_and_historical_localhost_port() -> None:
    module = load_module()
    for host in ("localhost", "0.0.0.0", "192.0.2.1", "::1"):
        with pytest.raises(module.RedirectContractError) as error:
            module.resolve_installed_redirect(host, 1)
        assert error.value.code == "LOOPBACK_BIND_FAILED"


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
