"""Secure, offline-testable installed-application OAuth loopback redirect support.

The listener binds only to IPv4 loopback, accepts one root callback, and keeps
callback results redacted.  It never logs callback query values or renders them
in the browser response.
"""
from __future__ import annotations

import math
import socket
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit


LOOPBACK_HOST = "127.0.0.1"
_CALLBACK_PATH = "/"
_BROWSER_SUCCESS = b"Authorization complete. You may close this window."
_BROWSER_FAILURE = b"Authorization could not be completed. Return to the application."


class RedirectContractError(ValueError):
    """Raised when a loopback redirect cannot be safely bound or represented."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class _ParsedRedirect:
    uri: str
    port: int


def _raise_bind_failure() -> None:
    raise RedirectContractError("LOOPBACK_BIND_FAILED")


def _valid_port(port: Any, *, allow_zero: bool) -> bool:
    return type(port) is int and (
        (allow_zero and 0 <= port <= 65535)
        or (not allow_zero and 1 <= port <= 65535)
    )


def _canonical_redirect(uri: Any) -> _ParsedRedirect | None:
    if type(uri) is not str or not uri:
        return None
    try:
        parsed = urlsplit(uri)
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme != "http"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.hostname != LOOPBACK_HOST
        or parsed.query
        or parsed.fragment
        or parsed.path != _CALLBACK_PATH
        or port is None
        or not _valid_port(port, allow_zero=False)
        or parsed.netloc != f"{LOOPBACK_HOST}:{port}"
        or uri != f"http://{LOOPBACK_HOST}:{port}{_CALLBACK_PATH}"
    ):
        return None
    return _ParsedRedirect(uri=uri, port=port)


def resolve_installed_redirect(host: str = LOOPBACK_HOST, port: int = 0) -> str:
    """Return the canonical loopback URI, reserving an OS-selected port when needed."""
    if host != LOOPBACK_HOST or not _valid_port(port, allow_zero=True):
        _raise_bind_failure()

    if port == 0:
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            probe.bind((LOOPBACK_HOST, 0))
            port = int(probe.getsockname()[1])
        except OSError:
            _raise_bind_failure()
        finally:
            probe.close()
    return f"http://{LOOPBACK_HOST}:{port}{_CALLBACK_PATH}"


def validate_redirect_contract(
    redirect_uri: str | None = None,
    authorization_redirect_uri: str | None = None,
    exchange_redirect_uri: str | None = None,
    callback_redirect_uri: str | None = None,
    *,
    client_type: str = "installed",
) -> dict[str, object]:
    """Validate that every OAuth phase uses one exact canonical redirect URI."""
    if client_type != "installed":
        return {"accepted": False, "invariant_code": "CLIENT_TYPE_NOT_INSTALLED"}

    values = (
        redirect_uri,
        authorization_redirect_uri,
        exchange_redirect_uri,
        callback_redirect_uri,
    )
    parsed = tuple(_canonical_redirect(value) for value in values)
    if any(item is None for item in parsed):
        return {"accepted": False, "invariant_code": "REDIRECT_URI_MISSING"}

    assert all(item is not None for item in parsed)
    if authorization_redirect_uri != exchange_redirect_uri:
        return {"accepted": False, "invariant_code": "AUTH_EXCHANGE_REDIRECT_MISMATCH"}
    if redirect_uri != authorization_redirect_uri:
        return {"accepted": False, "invariant_code": "AUTH_EXCHANGE_REDIRECT_MISMATCH"}
    if callback_redirect_uri != redirect_uri:
        return {"accepted": False, "invariant_code": "CALLBACK_REDIRECT_MISMATCH"}
    return {"accepted": True, "invariant_code": "REDIRECT_ACCEPTED"}


class OneShotCallbackListener:
    """A short-lived loopback server with a single terminal callback result."""

    def __init__(
        self,
        server: HTTPServer,
        state: str,
        redirect_uri: str,
        timeout: float,
    ) -> None:
        self._server = server
        self._state = state
        self.redirect_uri = redirect_uri
        self.uri = redirect_uri
        self.port = int(server.server_port)
        self.timeout = timeout
        self.thread = threading.Thread(
            target=self._serve,
            name=f"google-oauth-loopback-{self.port}",
            daemon=True,
        )
        self._lock = threading.Lock()
        self._done = threading.Event()
        self._ready = threading.Event()
        self._result: dict[str, object] | None = None
        self._authorization_code: str | None = None
        self._closed = False

    @property
    def socket(self) -> socket.socket | None:
        """Expose the live socket for cleanup assertions without exposing callbacks."""
        return getattr(self._server, "socket", None)

    @property
    def authorization_code(self) -> str | None:
        """Return the in-memory code only for the owning exchange consumer."""
        with self._lock:
            return self._authorization_code

    def start(self) -> None:
        self.thread.start()
        if not self._ready.wait(timeout=1.0):
            self.close()
            raise RedirectContractError("LOOPBACK_BIND_FAILED")

    def _serve(self) -> None:
        self._ready.set()
        # The server socket timeout keeps close() and expiry deterministic.
        self._server.timeout = min(0.1, self.timeout)
        stop_at = time.monotonic() + self.timeout
        try:
            while not self._done.is_set():
                if time.monotonic() >= stop_at:
                    self._finish("CALLBACK_EXPIRED")
                    break
                self._server.handle_request()
        finally:
            self._server.server_close()
            with self._lock:
                self._closed = True
                self._server.socket = None

    def _finish(self, invariant_code: str, authorization_code: str | None = None) -> None:
        with self._lock:
            if self._result is not None:
                return
            self._authorization_code = authorization_code
            self._result = {
                "accepted": invariant_code == "REDIRECT_ACCEPTED",
                "invariant_code": invariant_code,
            }
            self._done.set()

    def _consume_request(self, request_target: str, host_header: str | None) -> dict[str, object]:
        with self._lock:
            if self._result is not None:
                return {"accepted": False, "invariant_code": "SECOND_CALLBACK_REJECTED"}
        if host_header != f"{LOOPBACK_HOST}:{self.port}":
            self._finish("CALLBACK_REDIRECT_MISMATCH")
            return self._snapshot_result()
        parsed = urlsplit(request_target)
        if parsed.scheme or parsed.netloc or parsed.path != _CALLBACK_PATH:
            self._finish("CALLBACK_REDIRECT_MISMATCH")
            return self._snapshot_result()
        return self._consume_query(parsed.query)

    def _consume_query(self, query: str) -> dict[str, object]:
        with self._lock:
            if self._result is not None:
                return {"accepted": False, "invariant_code": "SECOND_CALLBACK_REJECTED"}
        params = parse_qs(query, keep_blank_values=True, strict_parsing=False)
        if "error" in params:
            self._finish("CALLBACK_OAUTH_ERROR")
        elif params.get("state") != [self._state]:
            self._finish("STATE_MISMATCH")
        elif (
            params.get("code") is None
            or params.get("code") != [params["code"][0]]
            or not params["code"][0]
        ):
            self._finish("CALLBACK_MISSING_CODE")
        else:
            self._finish("REDIRECT_ACCEPTED", params["code"][0])
        return self._snapshot_result()

    def _snapshot_result(self) -> dict[str, object]:
        with self._lock:
            return dict(self._result or {"accepted": False, "invariant_code": "CALLBACK_EXPIRED"})

    def wait(self, timeout: float | None = None) -> dict[str, object]:
        if not self.thread.is_alive() and self._result is None:
            self._finish("CALLBACK_EXPIRED")
        if self.thread.is_alive():
            self.thread.join(timeout)
        if self.thread.is_alive():
            raise TimeoutError("callback listener did not terminate")
        with self._lock:
            return dict(self._result or {"accepted": False, "invariant_code": "CALLBACK_EXPIRED"})

    def close(self) -> None:
        with self._lock:
            if self._result is None:
                self._result = {"accepted": False, "invariant_code": "CALLBACK_EXPIRED"}
                self._done.set()
        if self.thread.is_alive() and threading.current_thread() is not self.thread:
            self.thread.join(timeout=2.0)
        elif not self.thread.is_alive() and self.socket is not None:
            self._server.server_close()


class _CallbackHandler(BaseHTTPRequestHandler):
    def __init__(self, listener: OneShotCallbackListener, *args: Any, **kwargs: Any) -> None:
        self._listener = listener
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        result = self._listener._consume_request(self.path, self.headers.get("Host"))
        accepted = result["accepted"] is True
        body = _BROWSER_SUCCESS if accepted else _BROWSER_FAILURE
        self.send_response(200 if accepted else 400)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        del format, args


def start_one_shot_callback_listener(
    redirect_uri: str | None = None,
    state: str | None = None,
    *,
    host: str = LOOPBACK_HOST,
    port: int = 0,
    timeout: float = 120.0,
) -> OneShotCallbackListener:
    """Bind and start one local callback listener before returning its exact URI."""
    if type(state) is not str or not state:
        raise RedirectContractError("STATE_MISMATCH")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise RedirectContractError("CALLBACK_EXPIRED")
    if host != LOOPBACK_HOST or not _valid_port(port, allow_zero=True):
        _raise_bind_failure()

    expected = _canonical_redirect(redirect_uri) if redirect_uri is not None else None
    if redirect_uri is not None and expected is None:
        raise RedirectContractError("REDIRECT_URI_MISSING")
    if expected is not None:
        if port not in (0, expected.port):
            _raise_bind_failure()
        port = expected.port

    listener_ref: list[OneShotCallbackListener] = []

    def handler(*args: Any, **kwargs: Any) -> None:
        _CallbackHandler(listener_ref[0], *args, **kwargs)

    try:
        server = HTTPServer((LOOPBACK_HOST, port), handler)
    except OSError:
        _raise_bind_failure()
    actual_port = int(server.server_port)
    actual_uri = resolve_installed_redirect(LOOPBACK_HOST, actual_port)
    if expected is not None and expected.uri != actual_uri:
        server.server_close()
        _raise_bind_failure()
    listener = OneShotCallbackListener(server, state, actual_uri, float(timeout))
    listener_ref.append(listener)
    listener.start()
    return listener


def consume_callback_once(
    listener: OneShotCallbackListener,
    callback_uri: str,
) -> dict[str, object]:
    """Consume one synthetic callback using the same validation as the HTTP handler."""
    if not isinstance(listener, OneShotCallbackListener):
        raise TypeError("listener must be a OneShotCallbackListener")
    if type(callback_uri) is not str:
        return {"accepted": False, "invariant_code": "CALLBACK_REDIRECT_MISMATCH"}
    parsed = urlsplit(callback_uri)
    expected = urlsplit(listener.redirect_uri)
    if (
        parsed.scheme != expected.scheme
        or parsed.netloc != expected.netloc
        or parsed.path != expected.path
        or parsed.fragment
    ):
        listener._finish("CALLBACK_REDIRECT_MISMATCH")
        return listener._snapshot_result()
    return listener._consume_query(parsed.query)


__all__ = [
    "RedirectContractError",
    "OneShotCallbackListener",
    "consume_callback_once",
    "resolve_installed_redirect",
    "start_one_shot_callback_listener",
    "validate_redirect_contract",
]
