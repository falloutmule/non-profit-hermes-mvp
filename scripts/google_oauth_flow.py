"""Repository-owned, offline-testable OAuth loopback orchestration.

The caller supplies the OAuth client flow, pending-session store, and one-shot
exchange operation.  This seam owns the redirect invariant and returns only
redacted status diagnostics; opaque state, verifier, and callback code stay
inside the injected boundaries.
"""
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from typing import Any, Callable, Final, Protocol

try:  # Support both ``scripts`` imports and direct module loading in tests.
    from .google_oauth_redirect import start_one_shot_callback_listener
except ImportError:  # pragma: no cover - exercised when scripts is on sys.path.
    from google_oauth_redirect import start_one_shot_callback_listener


_DEFAULT_PENDING_TTL: Final[float] = 600.0


@dataclass(frozen=True)
class PendingOAuthSession:
    """Restricted pending state; no client, URL, token, or provider payload."""

    redirect_uri: str
    state: str
    verifier: str
    expires_at: float


class PendingSessionStore(Protocol):
    def save(self, payload: PendingOAuthSession) -> None: ...

    def load(self) -> PendingOAuthSession | None: ...

    def clear(self) -> None: ...


class AuthorizationFlow(Protocol):
    authorization_redirect_uri: str
    exchange_redirect_uri: str

    def authorization_url(self) -> str: ...


FlowFactory: Final = Callable[..., AuthorizationFlow]
Exchange: Final = Callable[[str, str, str], Any]
ListenerFactory: Final = Callable[..., Any]


def _result(accepted: bool, code: str, *, exchange_attempted: bool) -> dict[str, object]:
    return {
        "accepted": accepted,
        "invariant_code": code,
        "exchange_attempted": exchange_attempted,
    }


def _valid_opaque(value: Any) -> bool:
    return type(value) is str and bool(value)


def _valid_scopes(scopes: Any) -> bool:
    return type(scopes) is frozenset and all(type(scope) is str and bool(scope) for scope in scopes)


def run_oauth_exchange(
    *,
    scopes: frozenset[str],
    pending_store: PendingSessionStore,
    flow_factory: FlowFactory,
    exchange: Exchange,
    listener_factory: ListenerFactory = start_one_shot_callback_listener,
    state_factory: Callable[[], str] = lambda: secrets.token_urlsafe(32),
    verifier_factory: Callable[[], str] = lambda: secrets.token_urlsafe(48),
    now: Callable[[], float] = time.time,
    port: int = 0,
    timeout: float = 120.0,
    pending_ttl: float = _DEFAULT_PENDING_TTL,
) -> dict[str, object]:
    """Bind once, construct authorization, validate one callback, and exchange once.

    ``flow_factory`` receives the listener's exact immutable URI only after the
    listener factory has been called with port zero.  The exchange callable is
    invoked at most once and only after all five redirect values and derived
    state validation pass.  Exceptions from injected boundaries are intentionally
    reduced to stable codes so no opaque OAuth value reaches a result or error.
    """
    if not _valid_scopes(scopes):
        return _result(False, "SCOPES_INVALID", exchange_attempted=False)
    if type(port) is not int or port != 0:
        return _result(False, "LOOPBACK_BIND_FAILED", exchange_attempted=False)
    if type(timeout) not in (int, float) or timeout <= 0:
        return _result(False, "CALLBACK_EXPIRED", exchange_attempted=False)
    if type(pending_ttl) not in (int, float) or pending_ttl <= 0:
        return _result(False, "PENDING_SESSION_EXPIRED", exchange_attempted=False)

    try:
        state = state_factory()
        verifier = verifier_factory()
    except Exception:
        return _result(False, "OPAQUE_VALUE_GENERATION_FAILED", exchange_attempted=False)
    if not _valid_opaque(state) or not _valid_opaque(verifier):
        return _result(False, "OPAQUE_VALUE_GENERATION_FAILED", exchange_attempted=False)

    listener = None
    pending_saved = False
    try:
        try:
            # This is the first external seam: it must bind/start port zero before
            # authorization construction is allowed to run.
            listener = listener_factory(state=state, port=0, timeout=timeout)
            listener_uri = listener.redirect_uri
        except Exception:
            return _result(False, "LOOPBACK_BIND_FAILED", exchange_attempted=False)

        if not _valid_opaque(listener_uri):
            return _result(False, "REDIRECT_URI_MISSING", exchange_attempted=False)

        try:
            flow = flow_factory(
                redirect_uri=listener_uri,
                scopes=scopes,
                state=state,
                verifier=verifier,
            )
            # Construct the authorization request after binding.  Its returned
            # URL is deliberately discarded and never crosses this API boundary.
            flow.authorization_url()
        except Exception:
            return _result(False, "AUTHORIZATION_CONSTRUCTION_FAILED", exchange_attempted=False)

        try:
            pending = PendingOAuthSession(
                redirect_uri=listener_uri,
                state=state,
                verifier=verifier,
                expires_at=float(now()) + float(pending_ttl),
            )
            pending_store.save(pending)
            pending_saved = True
        except Exception:
            return _result(False, "PENDING_SESSION_SAVE_FAILED", exchange_attempted=False)

        try:
            callback = listener.wait(timeout=timeout)
        except Exception:
            return _result(False, "CALLBACK_FAILED", exchange_attempted=False)

        if type(callback) is not dict:
            return _result(False, "CALLBACK_INVALID", exchange_attempted=False)
        if callback.get("accepted") is not True:
            code = callback.get("invariant_code")
            return _result(
                False,
                code if type(code) is str and code else "CALLBACK_REJECTED",
                exchange_attempted=False,
            )

        try:
            persisted = pending_store.load()
        except Exception:
            return _result(False, "PENDING_SESSION_UNAVAILABLE", exchange_attempted=False)
        if type(persisted) is not PendingOAuthSession:
            return _result(False, "PENDING_SESSION_INVALID", exchange_attempted=False)
        try:
            if persisted.expires_at <= float(now()):
                return _result(False, "PENDING_SESSION_EXPIRED", exchange_attempted=False)
            if persisted.state != state or persisted.verifier != verifier:
                return _result(False, "PENDING_OPAQUE_VALUE_MISMATCH", exchange_attempted=False)
            if persisted.redirect_uri != listener_uri:
                return _result(False, "PENDING_REDIRECT_MISMATCH", exchange_attempted=False)

            callback_uri = callback.get("callback_redirect_uri")
            authorization_uri = getattr(flow, "authorization_redirect_uri", None)
            exchange_uri = getattr(flow, "exchange_redirect_uri", None)
        except Exception:
            return _result(False, "CALLBACK_VALIDATION_FAILED", exchange_attempted=False)
        if not all(_valid_opaque(value) for value in (callback_uri, authorization_uri, exchange_uri)):
            return _result(False, "REDIRECT_URI_MISSING", exchange_attempted=False)
        if callback_uri != listener_uri:
            return _result(False, "CALLBACK_REDIRECT_MISMATCH", exchange_attempted=False)
        if not (
            listener_uri == persisted.redirect_uri == authorization_uri == exchange_uri
        ):
            return _result(False, "AUTH_EXCHANGE_REDIRECT_MISMATCH", exchange_attempted=False)
        if callback.get("state_matches") is not True:
            return _result(False, "STATE_MISMATCH", exchange_attempted=False)

        code = getattr(listener, "authorization_code", None)
        if not _valid_opaque(code):
            return _result(False, "CALLBACK_MISSING_CODE", exchange_attempted=False)
        try:
            # One-shot by construction: there is exactly one call and no retry.
            exchange(code, exchange_uri, persisted.verifier)
        except Exception:
            return _result(False, "EXCHANGE_FAILED", exchange_attempted=True)
        return _result(True, "EXCHANGE_COMPLETED", exchange_attempted=True)
    finally:
        if pending_saved:
            try:
                pending_store.clear()
            except Exception:
                pass
        if listener is not None:
            try:
                listener.close()
            except Exception:
                pass


__all__ = ["PendingOAuthSession", "run_oauth_exchange"]
