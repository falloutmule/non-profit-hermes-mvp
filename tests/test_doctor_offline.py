"""Deterministic offline runtime-doctor contract tests."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
LEGACY_PLUGINS = (
    "non-profit-hermes-daily",
    "non-profit-hermes-need",
    "non-profit-hermes-donation",
    "non-profit-hermes-report",
    "non-profit-hermes-task",
    "non-profit-hermes-inventory",
    "non-profit-hermes-event",
)


def create_complete_profile(root: Path) -> tuple[Path, dict[str, str]]:
    profile = root / "profiles" / "nonprofit"
    plugin = profile / "plugins" / "non-profit-hermes"
    skill = profile / "skills" / "non-profit-hermes"
    plugin.mkdir(parents=True)
    skill.mkdir(parents=True)
    disabled = "\n".join(f"    - {name}" for name in LEGACY_PLUGINS)
    (profile / "distribution.yaml").write_text(
        """name: nonprofit
version: 1.0.0
hermes_requires: ">=0.18.2"
distribution_owned:
  - distribution.yaml
  - SOUL.md
  - config.yaml
  - skills/non-profit-hermes
  - plugins/non-profit-hermes
""",
        encoding="utf-8",
    )
    (profile / "SOUL.md").write_text("# Non-Profit Hermes\n", encoding="utf-8")
    (profile / "config.yaml").write_text(
        "model: openai-codex/gpt-5.6-sol\n"
        "plugins:\n"
        "  enabled:\n"
        "    - non-profit-hermes\n"
        "  disabled:\n"
        f"{disabled}\n",
        encoding="utf-8",
    )
    (profile / "auth.json").write_text(
        json.dumps({"openai-codex": {"refresh_token": "auth-value-sentinel"}}),
        encoding="utf-8",
    )
    (profile / ".env").write_text(
        "PRIVATE_RUNTIME_INPUT=dotenv-secret-sentinel\n", encoding="utf-8"
    )
    (skill / "SKILL.md").write_text(
        "---\nname: non-profit-hermes\nversion: 1.0.0\n---\n# Safe skill\n",
        encoding="utf-8",
    )
    (plugin / "plugin.yaml").write_text(
        "name: non-profit-hermes\nversion: 1.0.0\nkind: standalone\n",
        encoding="utf-8",
    )
    (plugin / "__init__.py").write_text("# safe plugin\n", encoding="utf-8")
    (plugin / "commands.py").write_text("# safe commands\n", encoding="utf-8")
    credentials = root / "private" / "google-credentials.json"
    credentials.parent.mkdir()
    credentials.write_text("must-not-be-read-sentinel", encoding="utf-8")
    environment = {
        "TELEGRAM_BOT_TOKEN": "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi_12345",
        "TELEGRAM_ALLOWED_USERS": "-1001234567890",
        "NON_PROFIT_HERMES_CREDENTIALS_FILE": str(credentials),
        "NON_PROFIT_HERMES_SPREADSHEET_ID": "sheet-private-sentinel",
        "NON_PROFIT_HERMES_CALENDAR_ID": "calendar-private-sentinel",
    }
    return profile, environment


def snapshot_tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_check_result_is_immutable_and_rejects_invalid_status_severity() -> None:
    from non_profit_hermes.diagnostics import CheckResult, Severity, Status

    result = CheckResult(
        id="package.version",
        category="package",
        status=Status.PASS,
        severity=Severity.HEALTHY,
        message="package version matches",
        metadata={"version": "1.0.0"},
    )

    assert result.status is Status.PASS
    assert result.severity is Severity.HEALTHY
    assert dict(result.metadata) == {"version": "1.0.0"}
    with pytest.raises(FrozenInstanceError):
        result.message = "changed"  # type: ignore[misc]
    with pytest.raises(ValueError, match="PASS and SKIP checks must be healthy"):
        CheckResult(
            id="package.version",
            category="package",
            status=Status.PASS,
            severity=Severity.WARNING,
            message="invalid",
        )
    with pytest.raises(ValueError, match="WARN checks must use warning severity"):
        CheckResult(
            id="package.version",
            category="package",
            status=Status.WARN,
            severity=Severity.CONFIGURATION,
            message="invalid",
        )
    with pytest.raises(ValueError, match="FAIL checks must be blocking"):
        CheckResult(
            id="package.version",
            category="package",
            status=Status.FAIL,
            severity=Severity.WARNING,
            message="invalid",
        )


def test_redaction_recursively_sanitizes_secret_chat_id_and_path_boundaries() -> None:
    from non_profit_hermes.diagnostics import redact

    secrets = {
        "token-value-sentinel",
        "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi_12345",
        "authorization-value-sentinel",
        "-1001234567890",
        "path-user-sentinel",
        "exception-password-sentinel",
        "ya29.google-access-sentinel",
        "AIzaSySyntheticGoogleApiKey0123456789012",
    }
    value = {
        "token": "token-value-sentinel",
        "nested": [
            "bot 123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi_12345",
            {"Authorization": "Bearer authorization-value-sentinel"},
            "chat_id=-1001234567890",
            "C:/Users/path-user-sentinel/private/auth.json",
            "RuntimeError: password=exception-password-sentinel",
            "ya29.google-access-sentinel",
            "AIzaSySyntheticGoogleApiKey0123456789012",
        ],
    }

    serialized = json.dumps(redact(value), sort_keys=True)

    assert all(secret not in serialized for secret in secrets)
    assert serialized.count("<redacted>") >= 6


def test_offline_runner_passes_complete_isolated_profile_without_writes_or_commands(
    tmp_path: Path,
) -> None:
    from non_profit_hermes.diagnostics import DoctorRunner, Status

    profile, environment = create_complete_profile(tmp_path / "hermes-home")
    before = snapshot_tree(tmp_path)

    def forbid_command(*args, **kwargs):
        raise AssertionError("offline runner invoked a command")

    report = DoctorRunner(
        profile="nonprofit",
        profile_root=profile,
        package_root=REPO_ROOT / "non_profit_hermes",
        distribution_root=profile,
        home=tmp_path / "home",
        environ=environment,
        command_adapter=forbid_command,
    ).run(mode="offline", strict=True)

    assert report.exit_code == 0
    assert [check.id for check in report.checks] == sorted(check.id for check in report.checks)
    assert all(check.status in {Status.PASS, Status.SKIP} for check in report.checks)
    assert {
        check.id for check in report.checks if check.status is Status.SKIP
    } == {
        "gateway.live",
        "google.live",
        "package.source_commit",
        "public_site.live",
        "telegram.live",
    }
    assert snapshot_tree(tmp_path) == before


def test_module_and_console_cli_emit_stable_redacted_json_and_human_output(
    tmp_path: Path,
) -> None:
    from non_profit_hermes import doctor
    from non_profit_hermes.diagnostics import DoctorRunner

    profile, environment = create_complete_profile(tmp_path / "hermes-home")
    runner = DoctorRunner(
        profile="nonprofit",
        profile_root=profile,
        package_root=REPO_ROOT / "non_profit_hermes",
        distribution_root=profile,
        home=tmp_path / "home",
        environ=environment,
        command_adapter=lambda *args: pytest.fail("unexpected command"),
    )
    forbidden = tuple(environment.values()) + (
        "auth-value-sentinel",
        "dotenv-secret-sentinel",
        "must-not-be-read-sentinel",
    )

    json_out = io.StringIO()
    json_err = io.StringIO()
    json_code = doctor.main(
        ["--json", "--offline", "--strict", "--profile", "nonprofit"],
        runner=runner,
        stdout=json_out,
        stderr=json_err,
    )
    payload = json.loads(json_out.getvalue())

    assert json_code == payload["exit_code"] == 0
    assert json_err.getvalue() == ""
    assert set(payload) == {
        "schema_version",
        "mode",
        "profile",
        "strict",
        "package_version",
        "summary",
        "checks",
        "exit_code",
    }
    assert payload["schema_version"] == 1
    assert [check["id"] for check in payload["checks"]] == sorted(
        check["id"] for check in payload["checks"]
    )
    assert all(secret not in json_out.getvalue() for secret in forbidden)

    human_out = io.StringIO()
    human_err = io.StringIO()
    human_code = doctor.console_main(
        ["doctor", "--offline", "--strict", "--profile", "nonprofit"],
        runner=runner,
        stdout=human_out,
        stderr=human_err,
    )
    lines = human_out.getvalue().splitlines()

    assert human_code == 0
    assert human_err.getvalue() == ""
    assert len(lines) == len(payload["checks"]) + 1
    assert lines[-1].startswith("RESULT healthy exit_code=0 ")
    assert all(secret not in human_out.getvalue() for secret in forbidden)


def test_module_rejects_console_only_doctor_token(tmp_path: Path) -> None:
    profile, environment = create_complete_profile(tmp_path / "hermes-home")
    stub_root = tmp_path / "stubs"
    hermes_cli = stub_root / "hermes_cli"
    hermes_cli.mkdir(parents=True)
    (hermes_cli / "__init__.py").write_text("", encoding="utf-8")
    (hermes_cli / "profiles.py").write_text(
        "from pathlib import Path\n"
        f"def get_profile_dir(name): return Path({str(profile)!r})\n",
        encoding="utf-8",
    )
    process_environment = os.environ.copy()
    process_environment.update(environment)
    process_environment["PYTHONPATH"] = os.pathsep.join((str(stub_root), str(REPO_ROOT)))
    result = subprocess.run(
        [sys.executable, "-m", "non_profit_hermes.doctor", "doctor", "--json"],
        cwd=REPO_ROOT,
        env=process_environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert "unrecognized arguments: doctor" in result.stderr


def test_exit_codes_are_exact_and_runtime_errors_serialize_without_details(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from non_profit_hermes import doctor
    from non_profit_hermes.diagnostics import DoctorRunner, LocalFilesystem, Status

    profile, environment = create_complete_profile(tmp_path / "hermes-home")
    base_arguments = {
        "profile": "nonprofit",
        "profile_root": profile,
        "package_root": REPO_ROOT / "non_profit_hermes",
        "distribution_root": profile,
        "home": tmp_path / "home",
        "environ": environment,
    }
    source = tmp_path / "source"
    source.mkdir()
    (source / ".git").write_text("gitdir: synthetic\n", encoding="utf-8")
    warning_runner = DoctorRunner(
        **base_arguments,
        source_root=source,
        command_adapter=lambda *args: SimpleNamespace(returncode=1, stdout="", stderr="ignored"),
    )

    warning = warning_runner.run(mode="offline", strict=False)
    strict_warning = warning_runner.run(mode="offline", strict=True)
    configuration = DoctorRunner(
        **{**base_arguments, "environ": {}},
        command_adapter=lambda *args: pytest.fail("unexpected command"),
    ).run(mode="offline")

    class ExplodingFilesystem(LocalFilesystem):
        def read_text(self, path: Path) -> str:
            if path.name == "models.py":
                raise RuntimeError(
                    "password=runtime-error-sentinel C:/Users/runtime-path-sentinel/private"
                )
            return super().read_text(path)

    runtime = DoctorRunner(
        **base_arguments,
        filesystem=ExplodingFilesystem(),
        command_adapter=lambda *args: pytest.fail("unexpected command"),
    ).run(mode="offline")
    (profile / "plugins" / "non-profit-hermes" / "commands.py").write_text(
        "BOT = '123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi_12345'\n",
        encoding="utf-8",
    )
    integrity = DoctorRunner(
        **base_arguments,
        command_adapter=lambda *args: pytest.fail("unexpected command"),
    ).run(mode="offline")

    assert warning.exit_code == 1
    assert strict_warning.exit_code == 2
    assert any(check.status is Status.WARN for check in strict_warning.checks)
    assert configuration.exit_code == 2
    assert runtime.exit_code == 3
    assert integrity.exit_code == 4
    runtime_json = doctor.render_json(runtime)
    assert "runtime-error-sentinel" not in runtime_json
    assert "runtime-path-sentinel" not in runtime_json
    assert "Traceback" not in runtime_json
