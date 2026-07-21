"""Sanitized contracts for read-only live integration diagnostics."""
from __future__ import annotations

from dataclasses import dataclass
import importlib
import json
import platform
from pathlib import Path
import re
import time
from types import ModuleType
from typing import Any, Callable, Mapping, Protocol, Sequence
from urllib.request import Request, urlopen as standard_urlopen

import yaml


class LiveProbeError(RuntimeError):
    """Base exception whose public contract exposes only a stable code and class."""

    code = "runtime"
    exit_code = 3


class LiveConfigurationError(LiveProbeError):
    code = "configuration"
    exit_code = 2


class LiveRuntimeError(LiveProbeError):
    code = "runtime"
    exit_code = 3


class LiveIntegrityError(LiveProbeError):
    code = "integrity"
    exit_code = 4


@dataclass(frozen=True)
class GatewaySnapshot:
    """Secret-free gateway, launcher, plugin, and listener observations."""

    scheduled_task_supported: bool
    scheduled_task_count: int
    scheduled_task_profile_selected: bool
    scheduled_task_secret_free: bool
    process_count: int
    pid_live: bool
    process_is_gateway: bool
    served_profile_matches: bool
    duplicate_poller: bool
    api_port_configured: bool
    api_port_unique: bool
    api_port_owned_by_gateway: bool
    restart_requested: bool
    error_retry_active: bool
    recent_start_count: int
    telegram_adapter_loaded: bool
    telegram_adapter_healthy: bool
    commands: tuple[str, ...]
    legacy_overlap: bool


@dataclass(frozen=True)
class TelegramSnapshot:
    """Secret-free Telegram getMe identity observations."""

    expected_username_configured: bool
    request_succeeded: bool
    identity_is_bot: bool
    username_matches: bool


@dataclass(frozen=True)
class GoogleSnapshot:
    """Count-free Google credential and minimal read observations."""

    credentials_valid: bool
    required_scopes_present: bool
    sheets_accessible: bool
    calendar_accessible: bool


@dataclass(frozen=True)
class PublicSiteSnapshot:
    """Secret-free local approved-safe and optional publication observations."""

    local_root_configured: bool
    required_files_present: bool
    local_marker_present: bool
    privacy_scan_clean: bool
    live_url_configured: bool
    live_marker_present: bool


class LiveProbeAdapter(Protocol):
    """Injected read-only integration boundary used only in live-readonly mode."""

    def probe_gateway(self) -> GatewaySnapshot: ...

    def probe_telegram(self) -> TelegramSnapshot: ...

    def probe_google(self) -> GoogleSnapshot: ...

    def probe_public_site(self) -> PublicSiteSnapshot: ...


class DefaultLiveProbeAdapter:
    """Fail-closed production adapter exposing read-only operations only."""

    def __init__(
        self,
        *,
        profile: str,
        profile_root: str | Path,
        environ: Mapping[str, str],
        filesystem: Any,
        command_adapter: Callable[[Sequence[str], Path], Any],
        platform_name: str | None = None,
        psutil_module: Any | None = None,
        urlopen: Callable[..., Any] | None = None,
        credentials_loader: Callable[..., Any] | None = None,
        service_builder: Callable[..., Any] | None = None,
    ) -> None:
        self.profile = profile
        self.profile_root = Path(profile_root)
        self.environ = dict(environ)
        self.fs = filesystem
        self.command_adapter = command_adapter
        self.platform_name = platform.system() if platform_name is None else platform_name
        self._psutil_module = psutil_module
        self._urlopen = standard_urlopen if urlopen is None else urlopen
        self._credentials_loader = credentials_loader
        self._service_builder = service_builder

    def _psutil(self) -> Any:
        if self._psutil_module is not None:
            return self._psutil_module
        try:
            return importlib.import_module("psutil")
        except (ImportError, ModuleNotFoundError) as error:
            raise LiveConfigurationError("psutil is unavailable") from error

    def _load_google_credentials(self, path: str, scopes: Sequence[str]) -> Any:
        if self._credentials_loader is not None:
            return self._credentials_loader(path, scopes)
        try:
            credentials_module = importlib.import_module("google.oauth2.credentials")
        except (ImportError, ModuleNotFoundError) as error:
            raise LiveConfigurationError("Google credential support is unavailable") from error
        return credentials_module.Credentials.from_authorized_user_file(path, scopes=scopes)

    def _build_google_service(self, name: str, version: str, **kwargs: Any) -> Any:
        if self._service_builder is not None:
            return self._service_builder(name, version, **kwargs)
        try:
            discovery = importlib.import_module("googleapiclient.discovery")
        except (ImportError, ModuleNotFoundError) as error:
            raise LiveConfigurationError("Google API client support is unavailable") from error
        return discovery.build(name, version, **kwargs)

    def _read_json_mapping(self, path: Path) -> Mapping[str, Any]:
        try:
            value = json.loads(self.fs.read_text(path))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise LiveRuntimeError("runtime state is unavailable") from error
        if not isinstance(value, Mapping):
            raise LiveIntegrityError("runtime state is invalid")
        return value

    def _read_profile_config(self) -> Mapping[str, Any]:
        try:
            value = yaml.safe_load(self.fs.read_text(self.profile_root / "config.yaml"))
        except (OSError, UnicodeError, yaml.YAMLError) as error:
            raise LiveConfigurationError("profile config is unavailable") from error
        if not isinstance(value, Mapping):
            raise LiveConfigurationError("profile config is invalid")
        return value

    def _scheduled_task_observation(self) -> tuple[bool, int, bool, bool]:
        if self.platform_name.casefold() != "windows":
            return False, 0, False, True
        result = self.command_adapter(
            ("schtasks", "/Query", "/FO", "CSV", "/V", "/NH"), self.profile_root
        )
        if getattr(result, "returncode", 1) != 0:
            raise LiveRuntimeError("Scheduled Task query failed")
        output = str(getattr(result, "stdout", ""))
        profile_patterns = (
            re.compile(rf"(?:--profile|-p)\s+{re.escape(self.profile)}(?:\s|$)", re.IGNORECASE),
            re.compile(rf"--profile={re.escape(self.profile)}(?:\s|$)", re.IGNORECASE),
            re.compile(rf"(?:^|[^A-Za-z0-9]){re.escape(self.profile)}(?:[^A-Za-z0-9]|$)", re.IGNORECASE),
        )
        matches = [
            line
            for line in output.splitlines()
            if "gateway" in line.casefold() and any(pattern.search(line) for pattern in profile_patterns)
        ]
        sensitive = re.compile(
            r"(?:\b\d{8,10}:[A-Za-z0-9_-]{30,}\b|bearer\s+\S+|(?:token|secret|password)\s*[=:]\s*\S+)",
            re.IGNORECASE,
        )
        return True, len(matches), len(matches) == 1, not any(sensitive.search(line) for line in matches)

    def _recent_start_count(self) -> int:
        """Count recent starts from the append-only ledger without updating it."""

        path = self.profile_root / "gateway-starts.log"
        if not self.fs.is_file(path):
            return 0
        try:
            values = tuple(
                float(line.strip())
                for line in self.fs.read_text(path).splitlines()
                if line.strip()
            )
        except (OSError, UnicodeError, ValueError):
            raise LiveIntegrityError("gateway start ledger is invalid")
        now = time.time()
        return sum(0 <= now - value <= 120 for value in values)

    def _plugin_commands(self, config: Mapping[str, Any]) -> tuple[tuple[str, ...], bool]:
        command_path = self.profile_root / "plugins" / "non-profit-hermes" / "commands.py"
        if not self.fs.is_file(command_path):
            raise LiveConfigurationError("unified plugin command module is missing")
        module_name = f"_non_profit_hermes_doctor_{id(self):x}"
        module = ModuleType(module_name)
        module.__file__ = str(command_path)
        module.__package__ = ""
        try:
            source = self.fs.read_text(command_path)
            exec(compile(source, str(command_path), "exec"), module.__dict__)
        except (OSError, UnicodeError, SyntaxError, Exception) as error:
            raise LiveIntegrityError("unified plugin command module is invalid") from error
        raw_commands = getattr(module, "COMMANDS", ())
        commands = tuple(
            item if isinstance(item, str) else str(getattr(item, "name", ""))
            for item in raw_commands
        )
        plugins = config.get("plugins")
        enabled = plugins.get("enabled", ()) if isinstance(plugins, Mapping) else ()
        legacy_overlap = any(
            name in enabled
            for name in (
                "non-profit-hermes-daily",
                "non-profit-hermes-need",
                "non-profit-hermes-donation",
                "non-profit-hermes-report",
                "non-profit-hermes-task",
                "non-profit-hermes-inventory",
                "non-profit-hermes-event",
            )
        )
        return commands, legacy_overlap

    def probe_gateway(self) -> GatewaySnapshot:
        """Read gateway files, process/listener state, task metadata, and plugin metadata."""

        config = self._read_profile_config()
        state = self._read_json_mapping(self.profile_root / "gateway_state.json")
        try:
            pid = int(self.fs.read_text(self.profile_root / "gateway.pid").strip())
        except (OSError, UnicodeError, ValueError) as error:
            raise LiveRuntimeError("gateway PID is unavailable") from error

        psutil = self._psutil()
        matching: list[tuple[int, tuple[str, ...]]] = []
        for process in psutil.process_iter(["pid", "cmdline"]):
            info = getattr(process, "info", {})
            command = tuple(str(part) for part in (info.get("cmdline") or ()))
            lowered = tuple(part.casefold() for part in command)
            joined = " ".join(lowered)
            profile_selected = (
                f"--profile {self.profile.casefold()}" in joined
                or f"--profile={self.profile.casefold()}" in joined
                or f"-p {self.profile.casefold()}" in joined
            )
            if "gateway" in lowered or " gateway " in f" {joined} ":
                if profile_selected:
                    matching.append((int(info.get("pid", -1)), command))

        configured_port = config.get("API_SERVER_PORT")
        if configured_port is None and isinstance(config.get("api_server"), Mapping):
            configured_port = config["api_server"].get("port")
        try:
            api_port = int(configured_port)
            api_port_configured = 1 <= api_port <= 65535
        except (TypeError, ValueError):
            api_port = -1
            api_port_configured = False

        listeners = []
        if api_port_configured:
            for connection in psutil.net_connections(kind="inet"):
                local_address = getattr(connection, "laddr", None)
                if (
                    str(getattr(connection, "status", "")).upper().endswith("LISTEN")
                    and getattr(local_address, "port", None) == api_port
                ):
                    listeners.append(getattr(connection, "pid", None))

        task_supported, task_count, task_profile, task_secret_free = (
            self._scheduled_task_observation()
        )
        commands, legacy_overlap = self._plugin_commands(config)
        matching_pids = {item_pid for item_pid, _ in matching}
        platforms = state.get("platforms")
        platforms = platforms if isinstance(platforms, Mapping) else {}
        telegram = platforms.get("telegram", state.get("telegram_adapter"))
        telegram = telegram if isinstance(telegram, Mapping) else {}
        served_profiles = state.get("served_profiles")
        if isinstance(served_profiles, (list, tuple)):
            served_profile_matches = self.profile.casefold() in {
                str(item).casefold() for item in served_profiles
            }
        else:
            # Profile selection is independently established by the matching
            # runtime command and this profile-owned state-file location.
            served_profile_matches = pid in matching_pids
        telegram_state = str(telegram.get("state", "")).casefold()
        telegram_error = telegram.get("error_code")
        gateway_state = str(state.get("gateway_state", "")).casefold()
        recent_start_count = self._recent_start_count()
        return GatewaySnapshot(
            scheduled_task_supported=task_supported,
            scheduled_task_count=task_count,
            scheduled_task_profile_selected=task_profile,
            scheduled_task_secret_free=task_secret_free,
            process_count=len(matching),
            pid_live=pid in matching_pids,
            process_is_gateway=pid in matching_pids,
            served_profile_matches=served_profile_matches,
            duplicate_poller=len(matching) > 1,
            api_port_configured=api_port_configured,
            api_port_unique=len(listeners) == 1,
            api_port_owned_by_gateway=listeners == [pid],
            restart_requested=state.get("restart_requested") is True,
            error_retry_active=(
                state.get("error_retry_active") is True
                or gateway_state in {"error", "failed", "retrying"}
                or telegram_error not in {None, ""}
            ),
            recent_start_count=recent_start_count,
            telegram_adapter_loaded=(telegram.get("loaded") is True or bool(telegram_state)),
            telegram_adapter_healthy=(
                telegram.get("healthy") is True
                or (telegram_state in {"running", "healthy"} and telegram_error in {None, ""})
            ),
            commands=commands,
            legacy_overlap=legacy_overlap,
        )

    def probe_telegram(self) -> TelegramSnapshot:
        """Perform only Telegram's HTTPS getMe GET and discard all private identity data."""

        expected = self.environ.get("NON_PROFIT_HERMES_EXPECTED_BOT_USERNAME", "").strip()
        token = self.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        expected_configured = bool(expected)
        if not token or not expected_configured:
            return TelegramSnapshot(
                expected_username_configured=expected_configured,
                request_succeeded=False,
                identity_is_bot=False,
                username_matches=False,
            )
        request = Request(
            f"https://api.telegram.org/bot{token}/getMe",
            headers={"Accept": "application/json"},
            method="GET",
        )
        try:
            with self._urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception:
            return TelegramSnapshot(
                expected_username_configured=True,
                request_succeeded=False,
                identity_is_bot=False,
                username_matches=False,
            )
        result = payload.get("result") if isinstance(payload, Mapping) else None
        result = result if isinstance(result, Mapping) else {}
        username = result.get("username")
        expected_name = expected.removeprefix("@").casefold()
        return TelegramSnapshot(
            expected_username_configured=True,
            request_succeeded=payload.get("ok") is True,
            identity_is_bot=result.get("is_bot") is True,
            username_matches=isinstance(username, str) and username.casefold() == expected_name,
        )

    def probe_google(self) -> GoogleSnapshot:
        """Load unrefreshed authorized-user credentials and perform two minimal reads."""

        credential_path = self.environ.get("NON_PROFIT_HERMES_CREDENTIALS_FILE", "").strip()
        spreadsheet_id = self.environ.get("NON_PROFIT_HERMES_SPREADSHEET_ID", "").strip()
        calendar_id = self.environ.get("NON_PROFIT_HERMES_CALENDAR_ID", "").strip()
        if not credential_path or not spreadsheet_id or not calendar_id:
            return GoogleSnapshot(
                credentials_valid=False,
                required_scopes_present=False,
                sheets_accessible=False,
                calendar_accessible=False,
            )
        scopes = (
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/calendar.readonly",
        )
        try:
            credentials = self._load_google_credentials(credential_path, scopes)
        except LiveProbeError:
            raise
        except Exception:
            return GoogleSnapshot(False, False, False, False)
        credentials_valid = bool(getattr(credentials, "valid", False)) and not bool(
            getattr(credentials, "expired", False)
        )
        has_scopes = getattr(credentials, "has_scopes", None)
        required_scopes_present = bool(callable(has_scopes) and has_scopes(scopes))
        if not credentials_valid or not required_scopes_present:
            return GoogleSnapshot(
                credentials_valid=credentials_valid,
                required_scopes_present=required_scopes_present,
                sheets_accessible=False,
                calendar_accessible=False,
            )

        sheets_accessible = False
        calendar_accessible = False
        try:
            sheets = self._build_google_service(
                "sheets", "v4", credentials=credentials, cache_discovery=False
            )
            sheets.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id, range="A1:A1"
            ).execute(num_retries=0)
            sheets_accessible = True
        except LiveProbeError:
            raise
        except Exception:
            sheets_accessible = False
        try:
            calendar = self._build_google_service(
                "calendar", "v3", credentials=credentials, cache_discovery=False
            )
            calendar.calendarList().get(calendarId=calendar_id).execute(num_retries=0)
            calendar_accessible = True
        except LiveProbeError:
            raise
        except Exception:
            calendar_accessible = False
        return GoogleSnapshot(
            credentials_valid=True,
            required_scopes_present=True,
            sheets_accessible=sheets_accessible,
            calendar_accessible=calendar_accessible,
        )

    def probe_public_site(self) -> PublicSiteSnapshot:
        """Inspect only approved-safe files and optionally GET the HTTPS publication marker."""

        marker = "CLEAN_DOCS_DEPLOY_NON_PROFIT_HERMES_002"
        expected_files = (
            ".nojekyll",
            "index.html",
            "data/approved_needs.json",
            "data/approved_calendar.json",
            "data/approved_reports.json",
            "data/approved_donations.json",
            "data/approved_volunteer_gaps.json",
            "data/approved_board_log.json",
        )
        excluded_patterns = (
            re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{30,}\b"),
            re.compile(r"\bBearer\s+\S+", re.IGNORECASE),
            re.compile(
                r"\b(?:token|secret|password|authorization|cookie|api[_-]?key)"
                r"\s*[:=]\s*[^\s,;]+",
                re.IGNORECASE,
            ),
            re.compile(r"\bya" + r"29\.[A-Za-z0-9._-]+"),
            re.compile(r"\b1" + r"//[A-Za-z0-9._-]+"),
            re.compile(r"\bAI" + r"za[A-Za-z0-9_-]{20,}"),
            re.compile(
                r"\b(?:chat|telegram|user)[_-]?id\s*[:=]\s*[\"']?-?\d{8,15}\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(?:SensitiveDetails|PrivateLocation|PhoneNumber|StreetAddress)\b",
                re.IGNORECASE,
            ),
        )
        configured_root = self.environ.get("NON_PROFIT_HERMES_PUBLIC_DIR", "").strip()
        root_configured = bool(configured_root)
        required_files_present = False
        local_marker_present = False
        privacy_scan_clean = False
        if root_configured:
            root = Path(configured_root).expanduser()
            paths = tuple(root / relative for relative in expected_files)
            required_files_present = all(self.fs.is_file(path) for path in paths)
            if required_files_present:
                try:
                    contents = tuple(self.fs.read_text(path) for path in paths)
                except (OSError, UnicodeError):
                    contents = ()
                if contents:
                    local_marker_present = marker in contents[1]
                    privacy_scan_clean = not any(
                        pattern.search(content)
                        for content in contents
                        for pattern in excluded_patterns
                    )

        configured_url = self.environ.get("NON_PROFIT_HERMES_PUBLIC_SITE_URL", "").strip()
        live_url_configured = bool(configured_url)
        live_marker_present = False
        if live_url_configured:
            if not configured_url.casefold().startswith("https://"):
                raise LiveConfigurationError("public site URL must use HTTPS")
            request = Request(
                configured_url,
                headers={"Accept": "text/html"},
                method="GET",
            )
            try:
                with self._urlopen(request, timeout=5) as response:
                    live_marker_present = marker in response.read().decode("utf-8")
            except Exception:
                live_marker_present = False

        return PublicSiteSnapshot(
            local_root_configured=root_configured,
            required_files_present=required_files_present,
            local_marker_present=local_marker_present,
            privacy_scan_clean=privacy_scan_clean,
            live_url_configured=live_url_configured,
            live_marker_present=live_marker_present,
        )


__all__ = [
    "GatewaySnapshot",
    "GoogleSnapshot",
    "DefaultLiveProbeAdapter",
    "LiveConfigurationError",
    "LiveIntegrityError",
    "LiveProbeAdapter",
    "LiveProbeError",
    "LiveRuntimeError",
    "PublicSiteSnapshot",
    "TelegramSnapshot",
]
