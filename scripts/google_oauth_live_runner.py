"""Guarded, one-shot OAuth recovery runner.

This module is deliberately an adapter around the repository-owned OAuth flow.
It imports the active Google Workspace helper's scopes and credential paths,
keeps opaque OAuth values inside injectable boundaries, and only writes a
candidate through the repository ACL repair module.  The runner is dry in this
repository: tests use fakes; operators must explicitly invoke the CLI.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Final
from urllib.parse import urlsplit


_HELPER_DIR = Path(
    os.environ.get(
        "HERMES_GOOGLE_WORKSPACE_SCRIPTS",
        Path.home() / "AppData" / "Local" / "hermes" / "skills" / "productivity" / "google-workspace" / "scripts",
    )
).expanduser()
if str(_HELPER_DIR) not in sys.path:
    sys.path.insert(0, str(_HELPER_DIR))

# These are intentionally imported, not copied.  The helper is the source of
# truth for the active profile's exact request and credential locations.
from google_api import CLIENT_SECRET_PATH, SCOPES, TOKEN_PATH  # type: ignore[import-not-found]

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

try:
    from .google_oauth_acl import prepare_candidate as _prepare_candidate
    from .google_oauth_flow import PendingOAuthSession, run_oauth_exchange
    from .google_oauth_redirect import start_one_shot_callback_listener
except ImportError:  # pragma: no cover - direct script/module loading
    from google_oauth_acl import prepare_candidate as _prepare_candidate
    from google_oauth_flow import PendingOAuthSession, run_oauth_exchange
    from google_oauth_redirect import start_one_shot_callback_listener


DEFAULT_PENDING_PATH: Final[Path] = TOKEN_PATH.with_name("google_oauth_pending.json")
DEFAULT_CANDIDATE_PATH: Final[Path] = TOKEN_PATH.with_name("google_token.candidate.json")
DEFAULT_HANDOFF_PATH: Final[Path] = TOKEN_PATH.with_name("google_oauth_url_handoff.json")
DEFAULT_EVIDENCE_PATH: Final[Path] = Path(__file__).resolve().parents[1] / "GR_OAUTH_001_URL_EVIDENCE.json"


class RunnerInvariantError(RuntimeError):
    """Stable, redacted runner failure category."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class RunnerPaths:
    operational_token: Path = TOKEN_PATH
    client_secret: Path = CLIENT_SECRET_PATH
    pending: Path = DEFAULT_PENDING_PATH
    candidate: Path = DEFAULT_CANDIDATE_PATH
    url_handoff: Path = DEFAULT_HANDOFF_PATH
    evidence: Path = DEFAULT_EVIDENCE_PATH

    @property
    def scopes(self) -> tuple[str, ...]:
        """Expose the imported helper scope sequence to offline test fixtures."""
        return tuple(SCOPES)


DEFAULT_PATHS: Final[RunnerPaths] = RunnerPaths()


class FilePendingSessionStore:
    """Persist only the repository flow's restricted pending-session fields."""

    def __init__(
        self,
        path: os.PathLike[str] | str,
        reference: os.PathLike[str] | str,
        *,
        preparer: Callable[..., Path] = _prepare_candidate,
        acl_runner: Callable[..., str] | None = None,
        snapshotter: Callable[..., Any] | None = None,
    ) -> None:
        self.path = Path(path)
        self.reference = Path(reference)
        self._preparer = preparer
        self._acl_runner = acl_runner
        self._snapshotter = snapshotter

    def save(self, payload: PendingOAuthSession) -> None:
        if type(payload) is not PendingOAuthSession:
            raise RunnerInvariantError("PENDING_SESSION_INVALID")
        encoded = json.dumps(
            {
                "redirect_uri": payload.redirect_uri,
                "state": payload.state,
                "verifier": payload.verifier,
                "expires_at": payload.expires_at,
            },
            sort_keys=True,
        ).encode("utf-8")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        _acl_prepare(
            self._preparer,
            self.reference,
            self.path,
            encoded,
            runner=self._acl_runner,
            snapshotter=self._snapshotter,
        )

    def load(self) -> PendingOAuthSession | None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if type(data) is not dict or set(data) != {"redirect_uri", "state", "verifier", "expires_at"}:
                return None
            if not all(type(data[key]) is str and bool(data[key]) for key in ("redirect_uri", "state", "verifier")):
                return None
            if type(data["expires_at"]) not in (int, float):
                return None
            return PendingOAuthSession(
                redirect_uri=data["redirect_uri"],
                state=data["state"],
                verifier=data["verifier"],
                expires_at=float(data["expires_at"]),
            )
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def clear(self) -> None:
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass


class TransientUrlHandoff:
    """Expose one authorization URL through one restricted, non-repository file."""

    def __init__(
        self,
        path: os.PathLike[str] | str,
        reference: os.PathLike[str] | str,
        *,
        preparer: Callable[..., Path] = _prepare_candidate,
        acl_runner: Callable[..., str] | None = None,
        snapshotter: Callable[..., Any] | None = None,
    ) -> None:
        self.path = Path(path)
        self.reference = Path(reference)
        self._preparer = preparer
        self._acl_runner = acl_runner
        self._snapshotter = snapshotter
        self._published = False

    def publish(self, url: str) -> str:
        if self._published or self.path.exists():
            raise RunnerInvariantError("URL_HANDOFF_ALREADY_PUBLISHED")
        if type(url) is not str or not url or any(character.isspace() for character in url):
            raise RunnerInvariantError("AUTHORIZATION_URL_INVALID")
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise RunnerInvariantError("AUTHORIZATION_URL_INVALID")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        _acl_prepare(
            self._preparer,
            self.reference,
            self.path,
            url.encode("utf-8"),
            runner=self._acl_runner,
            snapshotter=self._snapshotter,
        )
        self._published = True
        return url

    def clear(self) -> None:
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass
        self._published = False


def _acl_prepare(
    preparer: Callable[..., Path],
    reference: Path,
    candidate: Path,
    data: bytes,
    *,
    runner: Callable[..., str] | None,
    snapshotter: Callable[..., Any] | None,
) -> Path:
    kwargs: dict[str, Any] = {}
    if runner is not None:
        kwargs["runner"] = runner
    if snapshotter is not None:
        kwargs["snapshotter"] = snapshotter
    return preparer(reference, candidate, data, **kwargs)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _redacted_result(code: str, *, exchange_attempted: bool = False) -> dict[str, object]:
    return {"accepted": False, "invariant_code": code, "exchange_attempted": exchange_attempted}


def _validate_scopes() -> None:
    if type(SCOPES) is not list or not SCOPES or any(type(scope) is not str or not scope for scope in SCOPES):
        raise RunnerInvariantError("SCOPES_INVALID")
    if len(set(SCOPES)) != len(SCOPES):
        raise RunnerInvariantError("SCOPES_INVALID")


def _client_identity_hash(path: Path) -> str:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        installed = payload.get("installed") if type(payload) is dict else None
        client_id = installed.get("client_id") if type(installed) is dict else None
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RunnerInvariantError("CLIENT_CONFIGURATION_INVALID") from exc
    if type(installed) is not dict or type(client_id) is not str or not client_id:
        raise RunnerInvariantError("CLIENT_CONFIGURATION_INVALID")
    return hashlib.sha256(client_id.encode("utf-8")).hexdigest()


def _preflight(paths: RunnerPaths) -> tuple[str, str]:
    try:
        _validate_scopes()
    except RunnerInvariantError:
        raise
    if not paths.client_secret.is_file():
        raise RunnerInvariantError("CLIENT_CONFIGURATION_MISSING")
    client_hash = _client_identity_hash(paths.client_secret)
    if not paths.operational_token.is_file():
        raise RunnerInvariantError("OPERATIONAL_TOKEN_MISSING")
    if paths.candidate.exists():
        raise RunnerInvariantError("CANDIDATE_PRESENT")
    if paths.pending.exists():
        raise RunnerInvariantError("PENDING_PRESENT")
    if paths.url_handoff.exists():
        raise RunnerInvariantError("URL_HANDOFF_PRESENT")
    try:
        baseline_hash = _sha256(paths.operational_token)
    except OSError as exc:
        raise RunnerInvariantError("OPERATIONAL_TOKEN_UNREADABLE") from exc
    return client_hash, baseline_hash


class GoogleAuthFlowAdapter:
    """Adapt google-auth-oauthlib while keeping exchange output redacted."""

    def __init__(
        self,
        flow: Any,
        *,
        handoff: TransientUrlHandoff,
        operational_token: os.PathLike[str] | str,
        candidate: os.PathLike[str] | str,
        baseline_hash: str,
        candidate_preparer: Callable[..., Path] = _prepare_candidate,
        acl_runner: Callable[..., str] | None = None,
        snapshotter: Callable[..., Any] | None = None,
    ) -> None:
        self._flow = flow
        self._handoff = handoff
        self._operational_token = Path(operational_token)
        self._candidate = Path(candidate)
        self._baseline_hash = baseline_hash
        self._candidate_preparer = candidate_preparer
        self._acl_runner = acl_runner
        self._snapshotter = snapshotter
        self._url_published = False
        self._fetch_called = False
        self.authorization_redirect_uri = getattr(flow, "authorization_redirect_uri", "")
        self.exchange_redirect_uri = getattr(flow, "exchange_redirect_uri", self.authorization_redirect_uri)

    @classmethod
    def from_client_secret(
        cls,
        *,
        client_secret: Path,
        scopes: list[str],
        redirect_uri: str,
        state: str,
        verifier: str,
        handoff: TransientUrlHandoff,
        operational_token: Path,
        candidate: Path,
        baseline_hash: str,
        candidate_preparer: Callable[..., Path] = _prepare_candidate,
        acl_runner: Callable[..., str] | None = None,
        snapshotter: Callable[..., Any] | None = None,
    ) -> "GoogleAuthFlowAdapter":
        from google_auth_oauthlib.flow import Flow

        flow = Flow.from_client_secrets_file(
            str(client_secret),
            scopes=scopes,
            redirect_uri=redirect_uri,
            state=state,
            code_verifier=verifier,
        )
        return cls(
            flow,
            handoff=handoff,
            operational_token=operational_token,
            candidate=candidate,
            baseline_hash=baseline_hash,
            candidate_preparer=candidate_preparer,
            acl_runner=acl_runner,
            snapshotter=snapshotter,
        )

    def authorization_url(self) -> str:
        if self._url_published:
            raise RunnerInvariantError("URL_HANDOFF_ALREADY_PUBLISHED")
        raw = self._flow.authorization_url(access_type="offline", prompt="consent")
        url = raw[0] if type(raw) is tuple and len(raw) == 2 else raw
        if type(url) is not str:
            raise RunnerInvariantError("AUTHORIZATION_URL_INVALID")
        self._handoff.publish(url)
        self._url_published = True
        return url

    def exchange(self, code: str, redirect_uri: str, verifier: str) -> None:
        del redirect_uri, verifier
        if self._fetch_called:
            raise RunnerInvariantError("EXCHANGE_RETRY_BLOCKED")
        self._fetch_called = True
        if _sha256(self._operational_token) != self._baseline_hash:
            raise RunnerInvariantError("OPERATIONAL_TOKEN_CHANGED")
        if self._candidate.exists():
            raise RunnerInvariantError("CANDIDATE_PRESENT")
        try:
            self._flow.fetch_token(code=code)
            if _sha256(self._operational_token) != self._baseline_hash:
                raise RunnerInvariantError("OPERATIONAL_TOKEN_CHANGED")
            credentials = self._flow.credentials
            serialized = json.loads(credentials.to_json())
            if type(serialized) is not dict:
                raise RunnerInvariantError("CANDIDATE_SERIALIZATION_FAILED")
            serialized.setdefault("type", "authorized_user")
            granted = getattr(credentials, "granted_scopes", None)
            if type(granted) is list and granted:
                serialized["scopes"] = list(granted)
            data = json.dumps(serialized, indent=2, sort_keys=True).encode("utf-8")
            _acl_prepare(
                self._candidate_preparer,
                self._operational_token,
                self._candidate,
                data,
                runner=self._acl_runner,
                snapshotter=self._snapshotter,
            )
            if not self._candidate.is_file():
                raise RunnerInvariantError("CANDIDATE_WRITE_FAILED")
            if _sha256(self._operational_token) != self._baseline_hash:
                raise RunnerInvariantError("OPERATIONAL_TOKEN_CHANGED")
        except RunnerInvariantError:
            self._candidate.unlink(missing_ok=True)
            raise
        except Exception as exc:
            self._candidate.unlink(missing_ok=True)
            raise RunnerInvariantError("EXCHANGE_FAILED") from exc


def _write_evidence(
    paths: RunnerPaths,
    *,
    client_hash: str,
    baseline_hash: str,
    state: str,
    redirect_uri: str | None,
    started_at: str,
    completed_at: str,
) -> None:
    if redirect_uri is None:
        return
    parsed = urlsplit(redirect_uri)
    canonical_redirect = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    if parsed.query or parsed.fragment:
        raise RunnerInvariantError("REDIRECT_URI_MISSING")
    payload = {
        "record_type": "GR-OAUTH-001_URL_EVIDENCE",
        "requested_scopes": list(SCOPES),
        "redirect_uri": canonical_redirect,
        "client_identity_hash": client_hash,
        "started_at": started_at,
        "completed_at": completed_at,
        "state_hash": hashlib.sha256(state.encode("utf-8")).hexdigest(),
        "baseline_op_token_hash": baseline_hash,
    }
    paths.evidence.parent.mkdir(parents=True, exist_ok=True)
    paths.evidence.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_guarded_oauth(
    paths: RunnerPaths = DEFAULT_PATHS,
    *,
    listener_factory: Callable[..., Any] = start_one_shot_callback_listener,
    flow_factory: Callable[..., Any] | None = None,
    candidate_preparer: Callable[..., Path] = _prepare_candidate,
    acl_runner: Callable[..., str] | None = None,
    snapshotter: Callable[..., Any] | None = None,
    state_factory: Callable[[], str] = lambda: secrets.token_urlsafe(32),
    verifier_factory: Callable[[], str] = lambda: secrets.token_urlsafe(48),
    now: Callable[[], float] = time.time,
    timeout: float = 120.0,
    pending_ttl: float = 600.0,
) -> dict[str, object]:
    """Run the repository OAuth exchange with all preflight and cleanup guards."""
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        client_hash, baseline_hash = _preflight(paths)
    except RunnerInvariantError as error:
        return _redacted_result(error.code)

    handoff = TransientUrlHandoff(
        paths.url_handoff,
        paths.operational_token,
        preparer=candidate_preparer,
        acl_runner=acl_runner,
        snapshotter=snapshotter,
    )
    pending_store = FilePendingSessionStore(
        paths.pending,
        paths.operational_token,
        preparer=candidate_preparer,
        acl_runner=acl_runner,
        snapshotter=snapshotter,
    )
    observed_state: list[str] = []
    observed_redirect: list[str] = []
    adapter_holder: list[Any] = []

    def tracked_state() -> str:
        state = state_factory()
        observed_state.append(state)
        return state

    def tracked_listener(**kwargs: Any) -> Any:
        listener = listener_factory(**kwargs)
        uri = getattr(listener, "redirect_uri", None)
        if type(uri) is str:
            observed_redirect.append(uri)
        return listener

    def make_flow(*, redirect_uri: str, scopes: frozenset[str], state: str, verifier: str) -> Any:
        if flow_factory is not None:
            adapter = flow_factory(
                redirect_uri=redirect_uri,
                scopes=scopes,
                state=state,
                verifier=verifier,
                handoff=handoff,
            )
        else:
            adapter = GoogleAuthFlowAdapter.from_client_secret(
                client_secret=paths.client_secret,
                scopes=SCOPES,
                redirect_uri=redirect_uri,
                state=state,
                verifier=verifier,
                handoff=handoff,
                operational_token=paths.operational_token,
                candidate=paths.candidate,
                baseline_hash=baseline_hash,
                candidate_preparer=candidate_preparer,
                acl_runner=acl_runner,
                snapshotter=snapshotter,
            )
        adapter_holder.append(adapter)
        return adapter

    def exchange(code: str, redirect_uri: str, verifier: str) -> None:
        if not adapter_holder:
            raise RunnerInvariantError("AUTHORIZATION_CONSTRUCTION_FAILED")
        adapter_holder[0].exchange(code, redirect_uri, verifier)

    try:
        result = run_oauth_exchange(
            scopes=frozenset(SCOPES),
            pending_store=pending_store,
            flow_factory=make_flow,
            exchange=exchange,
            listener_factory=tracked_listener,
            state_factory=tracked_state,
            verifier_factory=verifier_factory,
            now=now,
            port=0,
            timeout=timeout,
            pending_ttl=pending_ttl,
        )
        if result.get("accepted") is True and _sha256(paths.operational_token) != baseline_hash:
            result = _redacted_result("OPERATIONAL_TOKEN_CHANGED", exchange_attempted=True)
        return result
    except RunnerInvariantError as error:
        return _redacted_result(error.code, exchange_attempted=True)
    finally:
        completed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            _write_evidence(
                paths,
                client_hash=client_hash,
                baseline_hash=baseline_hash,
                state=observed_state[0] if observed_state else "",
                redirect_uri=observed_redirect[0] if observed_redirect else None,
                started_at=started_at,
                completed_at=completed_at,
            )
        except (OSError, RunnerInvariantError):
            pass
        handoff.clear()


def main() -> int:
    """Explicit CLI entry point; never prints an authorization URL or secret."""
    result = run_guarded_oauth(
        state_factory=lambda: secrets.token_urlsafe(32),
        verifier_factory=lambda: secrets.token_urlsafe(48),
        now=time.time,
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("accepted") is True else 1


run_live_oauth_recovery = run_guarded_oauth


__all__ = [
    "CLIENT_SECRET_PATH",
    "DEFAULT_PATHS",
    "FilePendingSessionStore",
    "GoogleAuthFlowAdapter",
    "PendingOAuthSession",
    "RunnerInvariantError",
    "RunnerPaths",
    "SCOPES",
    "TOKEN_PATH",
    "TransientUrlHandoff",
    "run_guarded_oauth",
    "run_live_oauth_recovery",
]


if __name__ == "__main__":  # pragma: no cover - explicit live operator entry point
    raise SystemExit(main())
