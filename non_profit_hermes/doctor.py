"""Command-line interface for deterministic Non-Profit Hermes diagnostics."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence, TextIO

from non_profit_hermes import __version__
from non_profit_hermes.diagnostics import (
    CheckResult,
    DoctorReport,
    DoctorRunner,
    Severity,
    Status,
    redact,
)


SCHEMA_VERSION = 1
_RESULT_NAMES = {
    0: "healthy",
    1: "warning",
    2: "configuration-failure",
    3: "runtime-failure",
    4: "privacy-integrity-failure",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nonprofit-hermes")
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--profile", default="nonprofit")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--offline", action="store_const", const="offline", dest="mode")
    modes.add_argument(
        "--live-readonly", action="store_const", const="live-readonly", dest="mode"
    )
    parser.set_defaults(mode="offline")
    return parser


def _check_to_dict(check: CheckResult) -> dict[str, Any]:
    return {
        "id": check.id,
        "category": check.category,
        "status": check.status.value,
        "severity": int(check.severity),
        "message": check.message,
        "metadata": redact(check.metadata),
    }


def report_to_dict(report: DoctorReport) -> dict[str, Any]:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "mode": report.mode,
        "profile": report.profile,
        "strict": report.strict,
        "package_version": report.package_version,
        "summary": dict(report.summary),
        "checks": [_check_to_dict(check) for check in report.checks],
        "exit_code": report.exit_code,
    }
    sanitized = redact(payload)
    assert isinstance(sanitized, dict)
    return sanitized


def render_json(report: DoctorReport) -> str:
    return json.dumps(report_to_dict(report), sort_keys=True, separators=(",", ":"))


def render_human(report: DoctorReport) -> str:
    lines = [
        f"[{check.status.value}] {check.id} category={check.category} "
        f"severity={int(check.severity)} {check.message}"
        for check in report.checks
    ]
    summary = report.summary
    result_name = _RESULT_NAMES.get(report.exit_code, "runtime-failure")
    lines.append(
        f"RESULT {result_name} exit_code={report.exit_code} "
        f"pass={summary.get('pass', 0)} warn={summary.get('warn', 0)} "
        f"fail={summary.get('fail', 0)} skip={summary.get('skip', 0)}"
    )
    return "\n".join(lines)


def _source_root() -> Path | None:
    candidate = Path(__file__).resolve().parents[1]
    if (candidate / "pyproject.toml").is_file() and (candidate / ".git").exists():
        return candidate
    return None


def _runtime_failure(profile: str, mode: str, strict: bool, error: Exception) -> DoctorReport:
    check = CheckResult(
        id="doctor.runtime",
        category="runtime",
        status=Status.FAIL,
        severity=Severity.RUNTIME,
        message=f"doctor raised {type(error).__name__}",
    )
    return DoctorReport(
        mode=mode,
        profile=profile,
        strict=strict,
        package_version=__version__,
        checks=(check,),
        exit_code=int(Severity.RUNTIME),
        summary={"pass": 0, "warn": 0, "fail": 1, "skip": 0},
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: DoctorRunner | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    output = sys.stdout if stdout is None else stdout
    error_output = sys.stderr if stderr is None else stderr
    parser = build_parser()
    if stderr is not None:
        parser._print_message = lambda message, file=None: error_output.write(message or "")
    raw_arguments = list(sys.argv[1:] if argv is None else argv)
    if __name__ != "__main__" and raw_arguments and raw_arguments[0] == "doctor":
        raw_arguments.pop(0)
    arguments = parser.parse_args(raw_arguments)
    active_runner = runner or DoctorRunner(
        profile=arguments.profile,
        source_root=_source_root(),
    )
    try:
        report = active_runner.run(mode=arguments.mode, strict=arguments.strict)
    except Exception as error:
        report = _runtime_failure(arguments.profile, arguments.mode, arguments.strict, error)
    rendered = render_json(report) if arguments.json_output else render_human(report)
    output.write(rendered + "\n")
    return report.exit_code


def console_main(
    argv: Sequence[str] | None = None,
    *,
    runner: DoctorRunner | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "doctor":
        arguments.pop(0)
    return main(arguments, runner=runner, stdout=stdout, stderr=stderr)


if __name__ == "__main__":
    raise SystemExit(main())
