"""Deterministic live-readonly runtime-doctor contract tests."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from types import SimpleNamespace
import time

import pytest

from test_doctor_offline import REPO_ROOT, create_complete_profile


EXPECTED_COMMANDS = (
    "daily",
    "need",
    "donation",
    "report",
    "task",
    "inventory",
    "event",
)


class HealthyAdapter:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def probe_gateway(self):
        from non_profit_hermes.live_diagnostics import GatewaySnapshot

        self.calls.append("gateway")
        return GatewaySnapshot(
            scheduled_task_supported=True,
            scheduled_task_count=1,
            scheduled_task_profile_selected=True,
            scheduled_task_secret_free=True,
            process_count=1,
            pid_live=True,
            process_is_gateway=True,
            served_profile_matches=True,
            duplicate_poller=False,
            api_port_configured=True,
            api_port_unique=True,
            api_port_owned_by_gateway=True,
            restart_requested=False,
            error_retry_active=False,
            recent_start_count=1,
            telegram_adapter_loaded=True,
            telegram_adapter_healthy=True,
            commands=EXPECTED_COMMANDS,
            legacy_overlap=False,
        )

    def probe_telegram(self):
        from non_profit_hermes.live_diagnostics import TelegramSnapshot

        self.calls.append("telegram")
        return TelegramSnapshot(
            expected_username_configured=True,
            request_succeeded=True,
            identity_is_bot=True,
            username_matches=True,
        )

    def probe_google(self):
        from non_profit_hermes.live_diagnostics import GoogleSnapshot

        self.calls.append("google")
        return GoogleSnapshot(
            credentials_valid=True,
            required_scopes_present=True,
            sheets_accessible=True,
            calendar_accessible=True,
        )

    def probe_public_site(self):
        from non_profit_hermes.live_diagnostics import PublicSiteSnapshot

        self.calls.append("public_site")
        return PublicSiteSnapshot(
            local_root_configured=True,
            required_files_present=True,
            local_marker_present=True,
            privacy_scan_clean=True,
            live_url_configured=True,
            live_marker_present=True,
        )


def _runner(tmp_path: Path, adapter: object):
    from non_profit_hermes.diagnostics import DoctorRunner

    profile, environment = create_complete_profile(tmp_path / "hermes-home")
    return DoctorRunner(
        profile="nonprofit",
        profile_root=profile,
        package_root=REPO_ROOT / "non_profit_hermes",
        distribution_root=profile,
        home=tmp_path / "home",
        environ=environment,
        command_adapter=lambda *args: pytest.fail("unexpected core command"),
        live_adapter=adapter,
    )


def test_healthy_injected_adapter_replaces_placeholders_with_granular_strict_checks(
    tmp_path: Path,
) -> None:
    from non_profit_hermes.diagnostics import Status
    from non_profit_hermes.live_diagnostics import GatewaySnapshot

    adapter = HealthyAdapter()
    report = _runner(tmp_path, adapter).run(mode="live-readonly", strict=True)

    assert report.exit_code == 0
    assert adapter.calls == ["gateway", "telegram", "google", "public_site"]
    checks = {check.id: check for check in report.checks}
    live_check_ids = {
        "gateway.scheduled_task",
        "gateway.singleton_profile",
        "gateway.api_port",
        "gateway.restart_loop",
        "gateway.telegram_adapter",
        "gateway.commands",
        "telegram.identity",
        "google.scopes",
        "google.sheets_read",
        "google.calendar_read",
        "public_site.local_files",
        "public_site.local_marker",
        "public_site.privacy",
        "public_site.publication_marker",
    }
    assert live_check_ids.issubset(checks)
    assert all(checks[check_id].status is Status.PASS for check_id in live_check_ids)
    assert not any(check.id.endswith(".live") for check in report.checks)

    snapshot = adapter.probe_gateway()
    with pytest.raises(FrozenInstanceError):
        snapshot.process_count = 2  # type: ignore[misc]
    assert isinstance(snapshot, GatewaySnapshot)


def test_missing_expected_bot_username_warns_and_strict_promotes_to_configuration(
    tmp_path: Path,
) -> None:
    from non_profit_hermes.diagnostics import Status

    def adapter_without_expected_username() -> HealthyAdapter:
        adapter = HealthyAdapter()
        healthy_probe = adapter.probe_telegram
        adapter.probe_telegram = lambda: replace(  # type: ignore[method-assign]
            healthy_probe(), expected_username_configured=False
        )
        return adapter

    report = _runner(tmp_path / "normal", adapter_without_expected_username()).run(
        mode="live-readonly", strict=False
    )
    strict_report = _runner(tmp_path / "strict", adapter_without_expected_username()).run(
        mode="live-readonly", strict=True
    )

    identity = next(check for check in report.checks if check.id == "telegram.identity")
    assert identity.status is Status.WARN
    assert report.exit_code == 1
    assert strict_report.exit_code == 2


@pytest.mark.parametrize(
    ("error_name", "expected_exit"),
    (
        ("LiveConfigurationError", 2),
        ("LiveRuntimeError", 3),
        ("LiveIntegrityError", 4),
    ),
)
def test_adapter_exceptions_use_safe_classification_without_exception_details(
    tmp_path: Path, error_name: str, expected_exit: int
) -> None:
    from non_profit_hermes import doctor
    from non_profit_hermes import live_diagnostics

    error_type = getattr(live_diagnostics, error_name)
    adapter = HealthyAdapter()

    def explode():
        raise error_type(
            "password=adapter-exception-sentinel "
            "C:/Users/adapter-path-sentinel/private/auth.json"
        )

    adapter.probe_google = explode  # type: ignore[method-assign]
    report = _runner(tmp_path, adapter).run(mode="live-readonly", strict=False)
    serialized = doctor.render_json(report)
    failed = next(check for check in report.checks if check.id == "google.probe")

    assert report.exit_code == expected_exit
    assert error_name in failed.message
    assert "adapter-exception-sentinel" not in serialized
    assert "adapter-path-sentinel" not in serialized
    assert "Traceback" not in serialized


def test_default_gateway_probe_uses_only_readonly_process_task_status_and_plugin_reads(
    tmp_path: Path,
) -> None:
    from non_profit_hermes.diagnostics import LocalFilesystem
    from non_profit_hermes.live_diagnostics import DefaultLiveProbeAdapter

    profile, environment = create_complete_profile(tmp_path / "hermes-home")
    config = (profile / "config.yaml").read_text(encoding="utf-8")
    (profile / "config.yaml").write_text(config + "API_SERVER_PORT: 9123\n", encoding="utf-8")
    (profile / "gateway.pid").write_text("42\n", encoding="utf-8")
    (profile / "gateway_state.json").write_text(
        """{"gateway_state":"running","restart_requested":false,"exit_reason":null,
"served_profiles":["nonprofit"],"platforms":{"telegram":{"state":"running","error_code":null}}}""",
        encoding="utf-8",
    )
    (profile / "gateway-starts.log").write_text(f"{time.time()}\n", encoding="utf-8")
    (profile / "plugins" / "non-profit-hermes" / "commands.py").write_text(
        "COMMANDS=('daily','need','donation','report','task','inventory','event')\n",
        encoding="utf-8",
    )
    process = SimpleNamespace(
        info={
            "pid": 42,
            "cmdline": ["python", "-m", "hermes_cli", "--profile", "nonprofit", "gateway", "run"],
        }
    )
    connection = SimpleNamespace(
        status="LISTEN", laddr=SimpleNamespace(port=9123), pid=42
    )
    fake_psutil = SimpleNamespace(
        process_iter=lambda attrs: (process,),
        net_connections=lambda kind: (connection,),
    )
    command_calls: list[tuple[tuple[str, ...], Path]] = []

    def readonly_command(arguments, cwd):
        command_calls.append((tuple(arguments), cwd))
        return SimpleNamespace(
            returncode=0,
            stdout='"Hermes_Gateway_nonprofit","wscript launch_nonprofit_gateway.vbs"\n',
            stderr="",
        )

    before = {
        path.relative_to(profile).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in profile.rglob("*")
        if path.is_file()
    }
    snapshot = DefaultLiveProbeAdapter(
        profile="nonprofit",
        profile_root=profile,
        environ=environment,
        filesystem=LocalFilesystem(),
        command_adapter=readonly_command,
        platform_name="Windows",
        psutil_module=fake_psutil,
    ).probe_gateway()
    after = {
        path.relative_to(profile).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in profile.rglob("*")
        if path.is_file()
    }

    assert snapshot == HealthyAdapter().probe_gateway()
    assert command_calls == [
        (("schtasks", "/Query", "/FO", "CSV", "/V", "/NH"), profile)
    ]
    assert before == after


def test_default_telegram_probe_performs_one_bounded_getme_get_and_discards_identity_data(
    tmp_path: Path,
) -> None:
    from non_profit_hermes.diagnostics import LocalFilesystem
    from non_profit_hermes.live_diagnostics import DefaultLiveProbeAdapter, TelegramSnapshot

    profile, environment = create_complete_profile(tmp_path / "hermes-home")
    environment["NON_PROFIT_HERMES_EXPECTED_BOT_USERNAME"] = "@ExpectedBot"
    calls: list[tuple[str, str, int]] = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"ok":true,"result":{"id":987654321,"is_bot":true,"username":"expectedbot"}}'

    def urlopen(request, timeout):
        calls.append((request.full_url, request.get_method(), timeout))
        return Response()

    snapshot = DefaultLiveProbeAdapter(
        profile="nonprofit",
        profile_root=profile,
        environ=environment,
        filesystem=LocalFilesystem(),
        command_adapter=lambda *args: pytest.fail("unexpected command"),
        urlopen=urlopen,
    ).probe_telegram()

    assert snapshot == TelegramSnapshot(
        expected_username_configured=True,
        request_succeeded=True,
        identity_is_bot=True,
        username_matches=True,
    )
    assert len(calls) == 1
    assert calls[0][1:] == ("GET", 5)
    assert calls[0][0].endswith("/getMe")
    assert "getUpdates" not in calls[0][0]
    assert "sendMessage" not in calls[0][0]
    assert "setMyCommands" not in calls[0][0]
    assert "987654321" not in repr(snapshot)


def test_default_google_probe_uses_valid_unrefreshed_credentials_and_exact_minimal_reads(
    tmp_path: Path,
) -> None:
    from non_profit_hermes.diagnostics import LocalFilesystem
    from non_profit_hermes.live_diagnostics import DefaultLiveProbeAdapter, GoogleSnapshot

    profile, environment = create_complete_profile(tmp_path / "hermes-home")
    credential_path = Path(environment["NON_PROFIT_HERMES_CREDENTIALS_FILE"])
    credential_before = (credential_path.read_bytes(), credential_path.stat().st_mtime_ns)
    ledger: list[tuple[object, ...]] = []

    class Credentials:
        valid = True
        expired = False
        scopes = (
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/calendar.readonly",
        )

        def refresh(self, *args, **kwargs):
            pytest.fail("credential refresh was attempted")

        def has_scopes(self, required):
            return set(required).issubset(self.scopes)

    credentials = Credentials()

    def load_credentials(path, scopes):
        ledger.append(("credentials.load", Path(path), tuple(scopes)))
        return credentials

    class Execute:
        def __init__(self, operation):
            self.operation = operation

        def execute(self, *, num_retries):
            ledger.append((self.operation, "execute", num_retries))
            return {"private": "discarded"}

    class Values:
        def get(self, **kwargs):
            ledger.append(("sheets.values.get", kwargs))
            return Execute("sheets.values.get")

        def __getattr__(self, name):
            pytest.fail(f"forbidden Sheets values method: {name}")

    class Spreadsheets:
        def values(self):
            return Values()

    class Sheets:
        def spreadsheets(self):
            return Spreadsheets()

    class CalendarList:
        def get(self, **kwargs):
            ledger.append(("calendar.calendarList.get", kwargs))
            return Execute("calendar.calendarList.get")

        def __getattr__(self, name):
            pytest.fail(f"forbidden Calendar method: {name}")

    class Calendar:
        def calendarList(self):
            return CalendarList()

    def build_service(name, version, **kwargs):
        ledger.append(("service.build", name, version, kwargs))
        assert kwargs == {"credentials": credentials, "cache_discovery": False}
        return Sheets() if name == "sheets" else Calendar()

    snapshot = DefaultLiveProbeAdapter(
        profile="nonprofit",
        profile_root=profile,
        environ=environment,
        filesystem=LocalFilesystem(),
        command_adapter=lambda *args: pytest.fail("unexpected command"),
        credentials_loader=load_credentials,
        service_builder=build_service,
    ).probe_google()

    assert snapshot == GoogleSnapshot(
        credentials_valid=True,
        required_scopes_present=True,
        sheets_accessible=True,
        calendar_accessible=True,
    )
    assert [entry[0] for entry in ledger] == [
        "credentials.load",
        "service.build",
        "sheets.values.get",
        "sheets.values.get",
        "service.build",
        "calendar.calendarList.get",
        "calendar.calendarList.get",
    ]
    assert credential_before == (credential_path.read_bytes(), credential_path.stat().st_mtime_ns)


def test_default_public_site_probe_scans_only_expected_files_and_gets_https_marker_without_writes(
    tmp_path: Path,
) -> None:
    from non_profit_hermes.diagnostics import LocalFilesystem
    from non_profit_hermes.live_diagnostics import DefaultLiveProbeAdapter, PublicSiteSnapshot

    profile, environment = create_complete_profile(tmp_path / "hermes-home")
    public_root = tmp_path / "public"
    data_root = public_root / "data"
    data_root.mkdir(parents=True)
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
    for relative in expected_files:
        path = public_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(marker if relative == "index.html" else "[]", encoding="utf-8")
    # An unexpected file is deliberately outside the approved scan allowlist.
    (public_root / "unrelated.bin").write_bytes(b"token=outside-allowlist")
    environment["NON_PROFIT_HERMES_PUBLIC_DIR"] = str(public_root)
    environment["NON_PROFIT_HERMES_PUBLIC_SITE_URL"] = "https://example.test/nonprofit/"
    calls: list[tuple[str, str, int]] = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return f"<html>{marker}</html>".encode()

    def urlopen(request, timeout):
        calls.append((request.full_url, request.get_method(), timeout))
        return Response()

    before = {
        path.relative_to(public_root).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in public_root.rglob("*")
        if path.is_file()
    }
    snapshot = DefaultLiveProbeAdapter(
        profile="nonprofit",
        profile_root=profile,
        environ=environment,
        filesystem=LocalFilesystem(),
        command_adapter=lambda *args: pytest.fail("unexpected command"),
        urlopen=urlopen,
    ).probe_public_site()
    after = {
        path.relative_to(public_root).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in public_root.rglob("*")
        if path.is_file()
    }

    assert snapshot == PublicSiteSnapshot(
        local_root_configured=True,
        required_files_present=True,
        local_marker_present=True,
        privacy_scan_clean=True,
        live_url_configured=True,
        live_marker_present=True,
    )
    assert calls == [("https://example.test/nonprofit/", "GET", 5)]
    assert before == after
