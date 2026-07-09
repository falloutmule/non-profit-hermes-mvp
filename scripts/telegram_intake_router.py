"""
telegram_intake_router.py — Safe Telegram-style intake router for Non-Profit Hermes.

This script maps command-like Telegram text to the tested backend write module
in scripts/non_profit_hermes_ops.py. It does not register live Telegram
commands by itself; it provides a safe callable/router surface and a test mode.

CLI:
    python scripts/telegram_intake_router.py --test
    python scripts/telegram_intake_router.py --message "/daily"
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(r"C:\Users\fallo\non-profit-hermes-mvp")
SCRIPTS = ROOT / "scripts"
DOCS_DATA = ROOT / "docs" / "data"
STATE_DIR = Path.home() / "AppData" / "Local" / "hermes" / "state"
ACTIVE_NEED_STATE_PATH = STATE_DIR / "telegram_active_need_drafts.json"
SYNC_SCRIPT = SCRIPTS / "sync_approved_safe_data.py"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import non_profit_hermes_ops as ops  # noqa: E402

UNKNOWN = "unknown"
SOURCE_PREFIX = "telegram-simulated"

SENSITIVE_PATTERNS = [
    r"\bSensitiveNotes\b",
    r"\bmedical\b",
    r"\baddiction\b",
    r"\blegal\b",
    r"\bcamp\b",
    r"\bfamily crisis\b",
    r"\bprivate[- ]?location\b",
    r"\baddress\b",
    r"\bphone\b",
    r"\b\d{3}[-. ]?\d{3}[-. ]?\d{4}\b",
]
SENSITIVE_RE = re.compile("|".join(SENSITIVE_PATTERNS), re.IGNORECASE)

COMMANDS = {
    "/need",
    "/donation",
    "/report",
    "/task",
    "/inventory",
    "/event",
    "/daily",
}


@dataclass
class RouterResult:
    ok: bool
    command: str
    status: str
    message: str
    record_id: str = ""
    calendar_event_id: str = ""
    missing_fields: list[str] | None = None
    privacy_level: str = "board-visible"
    sensitive_hold: bool = False
    summary: str = ""
    backend_status: str = ""  # "created" | "already_exists" | "held" | "needs_more_info"

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "command": self.command,
            "status": self.status,
            "message": self.message,
            "record_id": self.record_id,
            "calendar_event_id": self.calendar_event_id,
            "missing_fields": self.missing_fields or [],
            "privacy_level": self.privacy_level,
            "sensitive_hold": self.sensitive_hold,
            "summary": self.summary,
            "backend_status": self.backend_status,
        }


def _example_for_command(command: str) -> str:
    """Return a safe example for the given command's missing-fields reply."""
    examples = {
        "/need": '/need id=REQ-EXAMPLE-001 description="Short safe need" urgency=normal needed_by=unknown location="public-safe area" privacy_level=board-visible next_action=review',
        "/donation": '/donation id=DON-EXAMPLE-001 item="Safe test donation" type=clothing quantity=1 condition=new pickup_or_dropoff=dropoff location="safe area" receipt_needed=no consent_to_public_thanks=yes next_action=review',
        "/report": '/report type=pantry summary="Pantry gave out socks and toilet paper" date=today people_served_estimate=unknown items_distributed="socks, toilet paper" followups_needed=none privacy_level=board-visible public_summary_allowed=yes next_action=review',
        "/task": '/task id=TASK-EXAMPLE-001 title="Safe test task" description="Verify task write" category=test priority=low due=2099-01-01',
        "/inventory": '/inventory id=INV-EXAMPLE-001 item="Safe test item" category=other quantity=10 unit=items minimum=5',
        "/event": '/event id=CAL-EXAMPLE-001 title="Safe test event" start=2099-01-01T09:00:00 end=2099-01-01T10:00:00',
    }
    return examples.get(
        command,
        f'{command} id=EXAMPLE-001 description="Safe example"',
    )


def _result_to_text(result: "RouterResult") -> str:
    """Render a RouterResult as a board-safe Telegram reply."""
    if result.summary:
        # /daily returns the full summary; pass it through unchanged.
        return result.summary
    if not result.ok and result.status == "needs_more_info":
            missing = ", ".join(result.missing_fields)
            cmd = result.command.lstrip("/")
            label = cmd.title() if cmd else "Record"
            example = _example_for_command(result.command)
            return (
                f"Need more info to create this {label}.\n"
                f"Missing: {missing}\n\n"
                f"Example:\n{example}"
            )
    if not result.ok and result.sensitive_hold:
        return result.message
    if result.ok and result.backend_status == "already_exists":
        return f"Request {result.record_id} already exists; duplicate skipped (no new row written)."
    if result.ok and result.status in {"needs-info", "draft"}:
        missing = ", ".join(result.missing_fields or []) or "none"
        label = result.command.lstrip("/").title() if result.command else "Record"
        return (
            f"Draft {label} created: {result.record_id}\n"
            f"Privacy: {result.privacy_level}\n"
            f"Status: {result.status}\n"
            f"Missing: {missing}\n"
            f"Next action: review"
        )
    if result.ok:
        label = result.command.lstrip("/").title() if result.command else "Record"
        return (
            f"{label} created: {result.record_id}\n"
            f"Privacy: {result.privacy_level}\n"
            f"Status: {result.backend_status}\n"
            f"Run /daily to see board summary, or visit the appropriate page."
        )
    return result.message


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_message(text: str) -> tuple[str, dict[str, str], str]:
    """Parse /command key=value text. Quoted values are supported via shlex."""
    text = text.strip()
    if not text:
        return "", {}, ""
    parts = shlex.split(text)
    if not parts:
        return "", {}, ""
    command = parts[0].lower()
    fields: dict[str, str] = {}
    free_parts: list[str] = []
    for token in parts[1:]:
        if "=" in token:
            key, value = token.split("=", 1)
            fields[key.strip().lower().replace("-", "_")] = value.strip()
        else:
            free_parts.append(token)
    return command, fields, " ".join(free_parts).strip()


def classify_privacy(text: str) -> tuple[str, bool, list[str]]:
    """Return (privacy_level, sensitive_hold, matched_terms)."""
    matches = sorted({m.group(0) for m in SENSITIVE_RE.finditer(text or "")})
    if matches:
        return "private-hold", True, matches
    return "board-visible", False, []


def missing_required(fields: dict[str, str], required: list[str]) -> list[str]:
    return [name for name in required if not fields.get(name)]


def normalize_need_description(text: str) -> str:
    """Normalize sloppy /need free text into a readable request description."""
    desc = (text or "").strip()
    desc = re.sub(r"\s*,\s*", " and ", desc)
    desc = re.sub(r"\b(\d+)\s+person\b", r"\1-person", desc, flags=re.IGNORECASE)
    desc = re.sub(r"\s+", " ", desc).strip()
    return desc


def generate_live_request_id(svc) -> str:
    """Generate REQ-LIVE-YYYYMMDD-### from existing Requests rows."""
    today = now_utc().strftime("%Y%m%d")
    prefix = f"REQ-LIVE-{today}-"
    try:
        rows = svc.spreadsheets().values().get(
            spreadsheetId=ops.SPREADSHEET_ID,
            range="Requests!A1:A1000",
        ).execute().get("values", [])
    except Exception:
        rows = []
    max_seq = 0
    for row in rows[1:]:
        if not row:
            continue
        rid = str(row[0]).strip()
        if rid.startswith(prefix):
            try:
                max_seq = max(max_seq, int(rid.rsplit("-", 1)[-1]))
            except ValueError:
                pass
    return f"{prefix}{max_seq + 1:03d}"


def explicit_privacy_level(fields: dict[str, str]) -> str | None:
    raw = (fields.get("privacy_level") or fields.get("privacy") or "").strip().lower()
    if raw in {"board-visible", "public-safe", "board-visible-test", "private-review", "private-hold"}:
        return raw
    return None
def source_scope(source_link: str) -> str:
    """Return the chat/session scope prefix for a source link."""
    raw = (source_link or "").strip()
    if not raw:
        return ""
    parts = raw.split(":")
    if len(parts) >= 4 and parts[0].lower() == "telegram":
        return ":".join(parts[:-1])
    return raw



def load_active_need_state() -> dict[str, dict[str, str]]:
    if not ACTIVE_NEED_STATE_PATH.exists():
        return {}
    try:
        raw = json.loads(ACTIVE_NEED_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}



def save_active_need_state(state: dict[str, dict[str, str]]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    ACTIVE_NEED_STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")



def get_active_need_request_id(source_link: str) -> str:
    scope = source_scope(source_link)
    return load_active_need_state().get(scope, {}).get("active_need_request_id", "")



def set_active_need_request_id(source_link: str, request_id: str) -> None:
    if not request_id:
        return
    state = load_active_need_state()
    scope = source_scope(source_link)
    state[scope] = {
        "active_need_request_id": request_id,
        "updated_at": now_utc().isoformat(),
    }
    save_active_need_state(state)



def clear_active_need_request_id(source_link: str, request_id: str | None = None) -> None:
    state = load_active_need_state()
    scope = source_scope(source_link)
    entry = state.get(scope)
    if not entry:
        return
    current = entry.get("active_need_request_id", "")
    if request_id and current and current != request_id:
        return
    entry.pop("active_need_request_id", None)
    entry.pop("updated_at", None)
    if entry:
        state[scope] = entry
    else:
        state.pop(scope, None)
    save_active_need_state(state)


def get_active_donation_id(source_link: str) -> str:
    scope = source_scope(source_link)
    return load_active_need_state().get(scope, {}).get("active_donation_id", "")



def set_active_donation_id(source_link: str, donation_id: str) -> None:
    if not donation_id:
        return
    state = load_active_need_state()
    scope = source_scope(source_link)
    entry = state.get(scope, {})
    entry["active_donation_id"] = donation_id
    entry["updated_at"] = now_utc().isoformat()
    state[scope] = entry
    save_active_need_state(state)



def clear_active_donation_id(source_link: str, donation_id: str | None = None) -> None:
    state = load_active_need_state()
    scope = source_scope(source_link)
    entry = state.get(scope)
    if not entry:
        return
    current = entry.get("active_donation_id", "")
    if donation_id and current and current != donation_id:
        return
    entry.pop("active_donation_id", None)
    entry.pop("updated_at", None)
    if entry:
        state[scope] = entry
    else:
        state.pop(scope, None)
    save_active_need_state(state)



def get_active_report_id(source_link: str) -> str:
    scope = source_scope(source_link)
    return load_active_need_state().get(scope, {}).get("active_report_id", "")


def set_active_report_id(source_link: str, report_id: str) -> None:
    if not report_id:
        return
    state = load_active_need_state()
    scope = source_scope(source_link)
    entry = state.get(scope, {})
    entry["active_report_id"] = report_id
    entry["updated_at"] = now_utc().isoformat()
    state[scope] = entry
    save_active_need_state(state)


def clear_active_report_id(source_link: str, report_id: str | None = None) -> None:
    state = load_active_need_state()
    scope = source_scope(source_link)
    entry = state.get(scope)
    if not entry:
        return
    current = entry.get("active_report_id", "")
    if report_id and current and current != report_id:
        return
    entry.pop("active_report_id", None)
    entry.pop("updated_at", None)
    if entry:
        state[scope] = entry
    else:
        state.pop(scope, None)
    save_active_need_state(state)


def report_row_by_id(svc, report_id: str) -> dict[str, str] | None:
    rows = svc.spreadsheets().values().get(
        spreadsheetId=ops.SPREADSHEET_ID,
        range="Reports!A1:Z1000",
    ).execute().get("values", [])
    if not rows:
        return None
    header = [h.strip() for h in rows[0]]
    if "ReportID" not in header:
        return None
    ridx = header.index("ReportID")
    for row in rows[1:]:
        if len(row) > ridx and row[ridx].strip() == report_id:
            return {header[i]: row[i] if i < len(row) else "" for i in range(len(header))}
    return None


def open_report_drafts(svc, source_link: str) -> list[dict[str, str]]:
    scope = source_scope(source_link)
    rows = svc.spreadsheets().values().get(
        spreadsheetId=ops.SPREADSHEET_ID,
        range="Reports!A1:Z1000",
    ).execute().get("values", [])
    if not rows:
        return []
    header = [h.strip() for h in rows[0]]
    out: list[dict[str, str]] = []
    for row in rows[1:]:
        data = {header[i]: row[i] if i < len(row) else "" for i in range(len(header))}
        if str(data.get("Status", "")).strip().lower() not in {"needs-info", "draft"}:
            continue
        row_scope = source_scope(data.get("SourceMessageLink", ""))
        if scope and row_scope != scope:
            continue
        out.append(data)
    out.sort(key=lambda item: (parse_dt(item.get("LastUpdated", "")) or parse_dt(item.get("Date", "")) or now_utc(), item.get("ReportID", "")))
    return out


def resolve_report_followup_target(svc, source_link: str, fields: dict[str, str]) -> tuple[dict[str, str] | None, list[str]]:
    requested_id = fields.get("reportid") or fields.get("report_id") or fields.get("id")
    if requested_id:
        row = report_row_by_id(svc, requested_id)
        if row:
            return row, []
        return None, [f"ReportID {requested_id} not found"]

    active_id = get_active_report_id(source_link)
    if active_id:
        row = report_row_by_id(svc, active_id)
        if row and str(row.get("Status", "")).strip().lower() in {"needs-info", "draft"}:
            return row, []
        clear_active_report_id(source_link, active_id)

    drafts = open_report_drafts(svc, source_link)
    if not drafts:
        return None, ["open needs-info report draft in this chat/session"]
    if len(drafts) > 1:
        return None, ["multiple active report drafts: " + ", ".join(d.get("ReportID", "") for d in drafts if d.get("ReportID"))]
    return drafts[0], []


def donation_row_by_id(svc, donation_id: str) -> dict[str, str] | None:
    rows = svc.spreadsheets().values().get(
        spreadsheetId=ops.SPREADSHEET_ID,
        range="Donations!A1:Z1000",
    ).execute().get("values", [])
    if not rows:
        return None
    header = [h.strip() for h in rows[0]]
    if "DonationID" not in header:
        return None
    didx = header.index("DonationID")
    for row in rows[1:]:
        if len(row) > didx and row[didx].strip() == donation_id:
            return {header[i]: row[i] if i < len(row) else "" for i in range(len(header))}
    return None



def open_donation_drafts(svc, source_link: str) -> list[dict[str, str]]:
    scope = source_scope(source_link)
    rows = svc.spreadsheets().values().get(
        spreadsheetId=ops.SPREADSHEET_ID,
        range="Donations!A1:Z1000",
    ).execute().get("values", [])
    if not rows:
        return []
    header = [h.strip() for h in rows[0]]
    out: list[dict[str, str]] = []
    for row in rows[1:]:
        data = {header[i]: row[i] if i < len(row) else "" for i in range(len(header))}
        if str(data.get("Status", "")).strip().lower() not in {"needs-info", "draft"}:
            continue
        row_scope = source_scope(data.get("SourceMessageLink", ""))
        if scope and row_scope != scope:
            continue
        out.append(data)
    out.sort(key=lambda item: (parse_dt(item.get("LastUpdated", "")) or parse_dt(item.get("DateOffered", "")) or now_utc(), item.get("DonationID", "")))
    return out



def resolve_donation_followup_target(svc, source_link: str, fields: dict[str, str]) -> tuple[dict[str, str] | None, list[str]]:
    requested_id = fields.get("donationid") or fields.get("donation_id") or fields.get("id")
    if requested_id:
        row = donation_row_by_id(svc, requested_id)
        if row:
            return row, []
        return None, [f"DonationID {requested_id} not found"]

    active_id = get_active_donation_id(source_link)
    if active_id:
        row = donation_row_by_id(svc, active_id)
        if row and str(row.get("Status", "")).strip().lower() in {"needs-info", "draft"}:
            return row, []
        clear_active_donation_id(source_link, active_id)

    drafts = open_donation_drafts(svc, source_link)
    if not drafts:
        return None, ["open needs-info donation draft in this chat/session"]
    if len(drafts) > 1:
        return None, ["multiple active donation drafts: " + ", ".join(d.get("DonationID", "") for d in drafts if d.get("DonationID"))]
    return drafts[0], []



def request_row_by_id(svc, request_id: str) -> dict[str, str] | None:
    rows = svc.spreadsheets().values().get(
        spreadsheetId=ops.SPREADSHEET_ID,
        range="Requests!A1:Z1000",
    ).execute().get("values", [])
    if not rows:
        return None
    header = [h.strip() for h in rows[0]]
    if "RequestID" not in header:
        return None
    req_idx = header.index("RequestID")
    for row in rows[1:]:
        if len(row) > req_idx and row[req_idx].strip() == request_id:
            return {header[i]: row[i] if i < len(row) else "" for i in range(len(header))}
    return None



def open_need_drafts(svc, source_link: str) -> list[dict[str, str]]:
    scope = source_scope(source_link)
    rows = svc.spreadsheets().values().get(
        spreadsheetId=ops.SPREADSHEET_ID,
        range="Requests!A1:Z1000",
    ).execute().get("values", [])
    if not rows:
        return []
    header = [h.strip() for h in rows[0]]
    out: list[dict[str, str]] = []
    for row in rows[1:]:
        data = {header[i]: row[i] if i < len(row) else "" for i in range(len(header))}
        if str(data.get("Status", "")).strip().lower() not in {"needs-info", "draft"}:
            continue
        row_scope = source_scope(data.get("SourceMessageLink", ""))
        if scope and row_scope != scope:
            continue
        out.append(data)
    out.sort(key=lambda item: (parse_dt(item.get("LastUpdated", "")) or parse_dt(item.get("DateReceived", "")) or now_utc(), item.get("RequestID", "")))
    return out



def resolve_need_followup_target(svc, source_link: str, fields: dict[str, str]) -> tuple[dict[str, str] | None, list[str]]:
    requested_id = fields.get("requestid") or fields.get("request_id") or fields.get("id")
    if requested_id:
        row = request_row_by_id(svc, requested_id)
        if row:
            return row, []
        return None, [f"RequestID {requested_id} not found"]

    active_id = get_active_need_request_id(source_link)
    if active_id:
        row = request_row_by_id(svc, active_id)
        if row and str(row.get("Status", "")).strip().lower() in {"needs-info", "draft"}:
            return row, []
        clear_active_need_request_id(source_link, active_id)

    drafts = open_need_drafts(svc, source_link)
    if not drafts:
        return None, ["open needs-info draft in this chat/session"]
    if len(drafts) > 1:
        return None, ["multiple active drafts: " + ", ".join(d.get("RequestID", "") for d in drafts if d.get("RequestID"))]
    return drafts[0], []


def services():
    c = ops.get_creds()
    return ops.sheets(c), ops.calendar(c)


def parse_followup_text(text: str) -> tuple[dict[str, str], str]:
    """Parse a plain follow-up message into key=value fields plus free text."""
    fields: dict[str, str] = {}
    free_parts: list[str] = []
    for token in shlex.split(text.strip()):
        if "=" in token:
            key, value = token.split("=", 1)
            fields[key.strip().lower().replace("-", "_")] = value.strip()
        else:
            free_parts.append(token)
    return fields, " ".join(free_parts).strip()


def audit_hold(svc, command: str, reason: str, source_link: str = "") -> str:
    return ops.write_audit_log(
        svc,
        actor="Hermes Telegram Router",
        action="hold",
        target_system="Telegram intake router",
        target_item=command,
        before="incoming command",
        after=reason,
        result="held",
        error="",
        source_link=source_link,
    )


def audit_missing(svc, command: str, missing: list[str], source_link: str = "") -> str:
    return ops.write_audit_log(
        svc,
        actor="Hermes Telegram Router",
        action="needs-more-info",
        target_system="Telegram intake router",
        target_item=command,
        before="incoming command",
        after="missing fields: " + ", ".join(missing),
        result="needs_more_info",
        error="",
        source_link=source_link,
    )


def parse_dt(value: str) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def handle_message(text: str, *, source_link: str = "telegram-simulated:test") -> RouterResult:
    stripped = (text or "").strip()
    if stripped and not stripped.startswith("/"):
        svc, svc_cal = services()
        followup_result = route_report_followup(svc, stripped, source_link)
        if followup_result is not None:
            return followup_result
        followup_result = route_donation_followup(svc, stripped, source_link)
        if followup_result is not None:
            return followup_result
        followup_result = route_need_followup(svc, stripped, source_link)
        if followup_result is not None:
            return followup_result

    command, fields, free_text = parse_message(text)
    if command not in COMMANDS:
        return RouterResult(False, command or UNKNOWN, "unsupported", "Unsupported command. Supported: " + ", ".join(sorted(COMMANDS)))

    privacy_level, sensitive_hold, sensitive_terms = classify_privacy(text)
    svc, svc_cal = services()

    if sensitive_hold:
        audit_id = audit_hold(svc, command, "Sensitive intake held; matched terms: " + ", ".join(sensitive_terms), source_link)
        return RouterResult(
            False,
            command,
            "held_sensitive",
            f"Held for human review. Sensitive details were not published or written to public-safe fields. Audit: {audit_id}",
            privacy_level=privacy_level,
            sensitive_hold=True,
        )

    if command == "/daily":
        summary = run_daily_summary()
        return RouterResult(True, command, "summarized", "Daily board-facing summary generated.", summary=summary)

    handlers = {
        "/need": route_need,
        "/donation": route_donation,
        "/report": route_report,
        "/task": route_task,
        "/inventory": route_inventory,
        "/event": route_event,
    }
    return handlers[command](svc, svc_cal, fields, free_text, source_link, privacy_level)


def route_need_followup(svc, followup_text: str, source_link: str) -> RouterResult | None:
    """Attach a plain follow-up message to the newest open /need draft in the same session."""
    fields, free_text = parse_followup_text(followup_text)
    target, problems = resolve_need_followup_target(svc, source_link, fields)
    if not target:
        if problems and problems[0].startswith("multiple active drafts:"):
            return RouterResult(False, "/need", "needs_more_info", "Multiple active drafts found. Please name RequestID.", missing_fields=problems)
        return RouterResult(False, "/need", "needs_more_info", "No open needs-info draft found in this chat/session.", missing_fields=problems or ["open needs-info draft in this chat/session"])

    updates: dict[str, str] = {}

    if "description" in fields or "need_description" in fields:
        updates["need_description"] = fields.get("description", fields.get("need_description", ""))
    if "category" in fields or "need_category" in fields:
        updates["need_category"] = fields.get("category", fields.get("need_category", ""))
    if "quantity" in fields:
        updates["quantity"] = fields["quantity"]
    if "urgency" in fields:
        updates["urgency"] = fields["urgency"]
    if "needed_by" in fields:
        updates["needed_by"] = fields["needed_by"]
    if "location" in fields:
        updates["location_public_safe"] = fields["location"]
    if "location_public_safe" in fields:
        updates["location_public_safe"] = fields["location_public_safe"]
    if "location_private" in fields:
        updates["location_private"] = fields["location_private"]
    if "privacy_level" in fields:
        updates["privacy_level"] = fields["privacy_level"]
    if "next_action" in fields:
        updates["next_action"] = fields["next_action"]
    if "status" in fields:
        updates["status"] = fields["status"]

    current_notes = target.get("Notes", "").strip()
    note_parts = []
    if free_text:
        note_parts.append(free_text)
    tracked_keys = {"description", "need_description", "category", "need_category", "quantity", "urgency", "needed_by", "location", "location_public_safe", "location_private", "privacy_level", "next_action", "status", "requestid", "request_id", "id"}
    kv_parts = [f"{k}={v}" for k, v in fields.items() if k not in tracked_keys]
    if kv_parts:
        note_parts.append(" ".join(kv_parts))
    if note_parts:
        followup_note = "Follow-up: " + " | ".join(note_parts)
        updates["notes"] = f"{current_notes}\n{followup_note}" if current_notes else followup_note

    result = ops.update_request(
        svc,
        request_id=target.get("RequestID", ""),
        source=target.get("Source", "Telegram live intake"),
        submitted_by=target.get("SubmittedBy", "Telegram user"),
        person_or_group=target.get("PersonOrGroup", UNKNOWN),
        contact_method=target.get("ContactMethod", UNKNOWN),
        need_category=updates.get("need_category", target.get("NeedCategory", UNKNOWN)),
        need_description=updates.get("need_description", target.get("NeedDescription", UNKNOWN)),
        quantity=updates.get("quantity", target.get("Quantity", UNKNOWN)),
        location_private=updates.get("location_private", target.get("LocationPrivate", "")),
        location_public_safe=updates.get("location_public_safe", target.get("LocationPublicSafe", UNKNOWN)),
        urgency=updates.get("urgency", target.get("Urgency", UNKNOWN)),
        needed_by=updates.get("needed_by", target.get("NeededBy", UNKNOWN)),
        privacy_level=updates.get("privacy_level", target.get("PrivacyLevel", "private-review")),
        status=updates.get("status", target.get("Status", "needs-info")),
        next_action=updates.get("next_action", target.get("NextAction", "review")),
        notes=updates.get("notes", target.get("Notes", "")),
        created_by=target.get("CreatedBy", "Hermes Telegram Router"),
        source_link=source_link,
    )
    final_status = (updates.get("status") or target.get("Status", "")).strip().lower()
    if final_status == "ready":
        clear_active_need_request_id(source_link, target.get("RequestID", ""))
    elif final_status in {"needs-info", "draft"}:
        set_active_need_request_id(source_link, target.get("RequestID", ""))
    return RouterResult(
        True,
        "/need",
        result.get("status", "updated"),
        f"Attached follow-up to {target.get('RequestID', UNKNOWN)}.",
        record_id=target.get("RequestID", ""),
        privacy_level=target.get("PrivacyLevel", "board-visible"),
        backend_status=result.get("status", "updated"),
    )


def route_need(svc, _svc_cal, fields: dict[str, str], free_text: str, source_link: str, privacy_level: str) -> RouterResult:
    description = normalize_need_description(fields.get("description", "") or free_text)
    if not description:
        audit_missing(svc, "/need", ["description"], source_link)
        return RouterResult(False, "/need", "needs_more_info", "Need more info: description", missing_fields=["description"])

    request_id = fields.get("id") or generate_live_request_id(svc)
    explicit_privacy = explicit_privacy_level(fields)
    final_privacy = explicit_privacy or "private-review"
    location = fields.get("location", UNKNOWN)
    missing_followup = [
        name for name in ["urgency", "needed_by", "location", "privacy_level"]
        if not fields.get(name)
    ]
    status = fields.get("status") or ("needs-info" if missing_followup else "new")
    next_action = fields.get("next_action", "review")

    result = ops.add_request(
        svc,
        request_id=request_id,
        source="Telegram live intake" if source_link.startswith("telegram:live") else "Telegram simulated intake",
        submitted_by=fields.get("submitted_by", "Telegram user"),
        person_or_group=fields.get("person_or_group", UNKNOWN),
        contact_method=UNKNOWN,
        need_category=fields.get("category", UNKNOWN),
        need_description=description,
        quantity=fields.get("quantity", UNKNOWN),
        location_public_safe=location if final_privacy in {"board-visible", "public-safe", "board-visible-test"} else UNKNOWN,
        urgency=fields.get("urgency", UNKNOWN),
        needed_by=fields.get("needed_by", UNKNOWN),
        privacy_level=final_privacy,
        status=status,
        next_action=next_action,
        notes="Sloppy Telegram /need intake; missing fields marked unknown; human review required" if missing_followup else "Telegram /need intake",
        created_by="Hermes Telegram Router",
        source_link=source_link,
    )
    if result.get("status") == "created":
        if status in {"needs-info", "draft"}:
            set_active_need_request_id(source_link, result["id"])
        else:
            clear_active_need_request_id(source_link, result["id"])
    reply_status = status if result.get("status") == "created" else result.get("status", status)
    return RouterResult(
        True,
        "/need",
        reply_status,
        "Request row written through backend.",
        record_id=result["id"],
        missing_fields=missing_followup,
        privacy_level=final_privacy,
        backend_status=result.get("status", "created"),
    )


def route_donation_followup(svc, followup_text: str, source_link: str) -> RouterResult | None:
    """Attach a plain follow-up message to the newest open /donation draft in the same session."""
    fields, free_text = parse_followup_text(followup_text)
    target, problems = resolve_donation_followup_target(svc, source_link, fields)
    if not target:
        if problems and problems[0].startswith("multiple active donation drafts:"):
            return RouterResult(False, "/donation", "needs_more_info", "Multiple active donation drafts found. Please name DonationID.", missing_fields=problems)
        return RouterResult(False, "/donation", "needs_more_info", "No open donation draft found in this chat/session.", missing_fields=problems or ["open needs-info donation draft in this chat/session"])

    updates: dict[str, str] = {}
    if "description" in fields or "item" in fields or "item_description" in fields:
        updates["item_description"] = fields.get("description", fields.get("item", fields.get("item_description", "")))
    if "type" in fields or "donation_type" in fields:
        updates["donation_type"] = fields.get("type", fields.get("donation_type", ""))
    if "quantity" in fields:
        updates["quantity"] = fields["quantity"]
    if "condition" in fields:
        updates["condition"] = fields["condition"]
    if "pickup_or_dropoff" in fields or "method" in fields:
        updates["pickup_or_dropoff"] = fields.get("pickup_or_dropoff", fields.get("method", ""))
    if "location" in fields:
        updates["location"] = fields["location"]
    if "available_date" in fields or "available" in fields:
        updates["available_date"] = fields.get("available_date", fields.get("available", ""))
    if "receipt_needed" in fields:
        updates["receipt_needed"] = fields["receipt_needed"]
    if "thank_you_needed" in fields:
        updates["thank_you_needed"] = fields["thank_you_needed"]
    if "consent_to_public_thanks" in fields or "public_thanks" in fields:
        updates["consent_to_public_thanks"] = fields.get("consent_to_public_thanks", fields.get("public_thanks", ""))
    if "next_action" in fields:
        updates["next_action"] = fields["next_action"]
    if "status" in fields:
        updates["status"] = fields["status"]

    current_notes = target.get("Notes", "").strip()
    note_parts = []
    if free_text:
        note_parts.append(free_text)
    tracked_keys = {"description", "item", "item_description", "type", "donation_type", "quantity", "condition", "pickup_or_dropoff", "method", "location", "available_date", "available", "receipt_needed", "thank_you_needed", "consent_to_public_thanks", "public_thanks", "next_action", "status", "donationid", "donation_id", "id"}
    kv_parts = [f"{k}={v}" for k, v in fields.items() if k not in tracked_keys]
    if kv_parts:
        note_parts.append(" ".join(kv_parts))
    if note_parts:
        followup_note = "Follow-up: " + " | ".join(note_parts)
        updates["notes"] = f"{current_notes}\n{followup_note}" if current_notes else followup_note

    result = ops.update_donation(
        svc,
        donation_id=target.get("DonationID", ""),
        donor_name=target.get("DonorName", "Anonymous Telegram donor"),
        donor_contact=target.get("DonorContact", UNKNOWN),
        donation_type=updates.get("donation_type", target.get("DonationType", UNKNOWN)),
        item_description=updates.get("item_description", target.get("ItemDescription", UNKNOWN)),
        quantity=updates.get("quantity", target.get("Quantity", UNKNOWN)),
        condition=updates.get("condition", target.get("Condition", UNKNOWN)),
        pickup_or_dropoff=updates.get("pickup_or_dropoff", target.get("PickupOrDropoff", UNKNOWN)),
        location=updates.get("location", target.get("Location", UNKNOWN)),
        available_date=updates.get("available_date", target.get("AvailableDate", UNKNOWN)),
        status=updates.get("status", target.get("Status", "needs-info")),
        receipt_needed=updates.get("receipt_needed", target.get("ReceiptNeeded", UNKNOWN)),
        thank_you_needed=updates.get("thank_you_needed", target.get("ThankYouNeeded", UNKNOWN)),
        consent_to_public_thanks=updates.get("consent_to_public_thanks", target.get("ConsentToPublicThanks", UNKNOWN)),
        notes=updates.get("notes", target.get("Notes", "")),
        source_link=source_link,
    )
    final_status = (updates.get("status") or target.get("Status", "")).strip().lower()
    if final_status == "ready":
        clear_active_donation_id(source_link, target.get("DonationID", ""))
    elif final_status in {"needs-info", "draft"}:
        set_active_donation_id(source_link, target.get("DonationID", ""))
    return RouterResult(
        True,
        "/donation",
        result.get("status", "updated"),
        f"Attached follow-up to {target.get('DonationID', UNKNOWN)}.",
        record_id=target.get("DonationID", ""),
        privacy_level=target.get("PrivacyLevel", "private-review"),
        backend_status=result.get("status", "updated"),
    )



def route_donation(svc, _svc_cal, fields: dict[str, str], free_text: str, source_link: str, privacy_level: str) -> RouterResult:
    item_description = normalize_need_description(fields.get("item", "") or fields.get("description", "") or free_text)
    if not item_description:
        item_description = UNKNOWN
    donation_id = fields.get("donationid") or fields.get("donation_id") or fields.get("id") or ""
    missing_followup = [
        name for name in ["pickup_or_dropoff", "location", "available_date", "receipt_needed", "consent_to_public_thanks", "next_action"]
        if not fields.get(name)
    ]
    status = fields.get("status") or ("needs-info" if missing_followup else "new")
    result = ops.add_donation(
        svc,
        donation_id=donation_id,
        donor_name=fields.get("donor_name", "Anonymous Telegram donor"),
        donor_contact=UNKNOWN,
        donation_type=fields.get("type", fields.get("donation_type", UNKNOWN)),
        item_description=item_description,
        quantity=fields.get("quantity", UNKNOWN),
        condition=fields.get("condition", UNKNOWN),
        pickup_or_dropoff=fields.get("pickup_or_dropoff", fields.get("method", UNKNOWN)),
        location=fields.get("location", UNKNOWN),
        available_date=fields.get("available_date", fields.get("available", UNKNOWN)),
        status=status,
        receipt_needed=fields.get("receipt_needed", UNKNOWN),
        thank_you_needed=fields.get("thank_you_needed", UNKNOWN),
        consent_to_public_thanks=fields.get("consent_to_public_thanks", fields.get("public_thanks", UNKNOWN)),
        notes="Telegram /donation intake; missing fields marked unknown; human review required" if missing_followup else "Telegram /donation intake",
        source_link=source_link,
    )
    if result.get("status") == "created":
        if status in {"needs-info", "draft"}:
            set_active_donation_id(source_link, result["id"])
        else:
            clear_active_donation_id(source_link, result["id"])
    reply_status = status if result.get("status") == "created" else result.get("status", status)
    return RouterResult(
        True,
        "/donation",
        reply_status,
        "Donation row written through backend.",
        record_id=result["id"],
        missing_fields=missing_followup,
        privacy_level="private-review",
        backend_status=result.get("status", "created"),
    )



def route_report(
    svc, _svc_cal, fields: dict[str, str], free_text: str, source_link: str, privacy_level: str
) -> RouterResult:
    summary = (fields.get("summary") or fields.get("description") or free_text).strip()
    if not summary:
        audit_missing(svc, "/report", ["summary"], source_link)
        return RouterResult(
            False, "/report", "needs_more_info",
            "Need more info: summary/description",
            missing_fields=["summary"],
        )

    report_id = fields.get("reportid") or fields.get("report_id") or fields.get("id") or ""
    explicit_privacy = explicit_privacy_level(fields)
    final_privacy = explicit_privacy or "private-review"

    REPORT_MISSING = [
        "report_type",
        "date",
        "people_served_estimate",
        "items_distributed",
        "followups_needed",
        "privacy_level",
        "public_summary_allowed",
        "next_action",
    ]
    missing_followup = [name for name in REPORT_MISSING if not fields.get(name)]
    status = fields.get("status") or ("needs-info" if missing_followup else "new")
    next_action = fields.get("next_action", "review")
    report_type = fields.get("report_type") or fields.get("type") or UNKNOWN

    # PublicSummaryDraft only populated when privacy is board-visible or public-safe
    public_safe = final_privacy in {"board-visible", "public-safe", "board-visible-test"}
    public_summary_draft = summary if public_safe else ""

    result = ops.add_report(
        svc,
        report_id=report_id,
        submitted_by=fields.get("submitted_by", "Telegram user"),
        report_type=report_type,
        summary=summary,
        privacy_level=final_privacy,
        sensitive_details="",  # never auto-populate sensitive details
        source_link=source_link,
    )
    if result.get("status") == "created":
        if status in {"needs-info", "draft"}:
            set_active_report_id(source_link, result["id"])
        else:
            clear_active_report_id(source_link, result["id"])
    reply_status = status if result.get("status") == "created" else result.get("status", status)
    return RouterResult(
        True,
        "/report",
        reply_status,
        "Report row written through backend.",
        record_id=result["id"],
        missing_fields=missing_followup,
        privacy_level=final_privacy,
        backend_status=result.get("status", "created"),
    )


def route_report_followup(svc, followup_text: str, source_link: str) -> RouterResult | None:
    """Attach a plain follow-up message to the active /report draft in the same session."""
    fields, free_text = parse_followup_text(followup_text)
    target, problems = resolve_report_followup_target(svc, source_link, fields)
    if not target:
        if problems and problems[0].startswith("multiple active report drafts:"):
            return RouterResult(
                False, "/report", "needs_more_info",
                "Multiple active report drafts found. Please name ReportID.",
                missing_fields=problems,
            )
        return RouterResult(
            False, "/report", "needs_more_info",
            "No open report draft found in this chat/session.",
            missing_fields=problems or ["open needs-info report draft in this chat/session"],
        )

    updates: dict[str, str] = {}
    if "summary" in fields or "description" in fields:
        updates["summary"] = fields.get("summary", fields.get("description", ""))
    if "report_type" in fields or "type" in fields:
        updates["report_type"] = fields.get("report_type", fields.get("type", ""))
    if "date" in fields:
        updates["date"] = fields["date"]
    if "people_served_estimate" in fields:
        updates["people_served_estimate"] = fields["people_served_estimate"]
    if "items_distributed" in fields:
        updates["items_distributed"] = fields["items_distributed"]
    if "followups_needed" in fields:
        updates["followups_needed"] = fields["followups_needed"]
    if "privacy_level" in fields:
        updates["privacy_level"] = fields["privacy_level"]
    if "public_summary_allowed" in fields:
        updates["public_summary_allowed"] = fields["public_summary_allowed"]
    if "next_action" in fields:
        updates["next_action"] = fields["next_action"]
    if "status" in fields:
        updates["status"] = fields["status"]

    current_notes = target.get("Notes", "").strip()
    note_parts = []
    if free_text:
        note_parts.append(free_text)
    tracked_keys = {
        "summary", "description", "report_type", "type", "date", "people_served_estimate",
        "items_distributed", "followups_needed", "privacy_level", "public_summary_allowed",
        "next_action", "status", "reportid", "report_id", "id",
    }
    kv_parts = [f"{k}={v}" for k, v in fields.items() if k not in tracked_keys]
    if kv_parts:
        note_parts.append(" ".join(kv_parts))
    if note_parts:
        followup_note = "Follow-up: " + " | ".join(note_parts)
        updates["notes"] = f"{current_notes}\n{followup_note}" if current_notes else followup_note

    # Determine public_summary_draft based on privacy
    new_privacy = updates.get("privacy_level", target.get("PrivacyLevel", "private-review"))
    new_summary = updates.get("summary", target.get("Summary", ""))
    public_safe = new_privacy in {"board-visible", "public-safe", "board-visible-test"}

    result = ops.update_report(
        svc,
        report_id=target.get("ReportID", ""),
        submitted_by=target.get("SubmittedBy", "Telegram user"),
        report_type=updates.get("report_type", target.get("ReportType", UNKNOWN)),
        summary=updates.get("summary", target.get("Summary", UNKNOWN)),
        people_served_estimate=updates.get("people_served_estimate", target.get("PeopleServedEstimate", UNKNOWN)),
        items_distributed=updates.get("items_distributed", target.get("ItemsDistributed", UNKNOWN)),
        followups_needed=updates.get("followups_needed", target.get("FollowUpsNeeded", UNKNOWN)),
        sensitive_details=target.get("SensitiveDetails", ""),
        public_summary_draft=new_summary if public_safe else "",
        privacy_level=new_privacy,
        date=updates.get("date", target.get("Date", UNKNOWN)),
        next_action=updates.get("next_action", target.get("NextAction", "review")),
        status=updates.get("status", target.get("Status", "needs-info")),
        source_link=source_link,
    )
    final_status = (updates.get("status") or target.get("Status", "")).strip().lower()
    if final_status == "ready":
        clear_active_report_id(source_link, target.get("ReportID", ""))
    elif final_status in {"needs-info", "draft"}:
        set_active_report_id(source_link, target.get("ReportID", ""))
    return RouterResult(
        True,
        "/report",
        result.get("status", "updated"),
        f"Attached follow-up to {target.get('ReportID', UNKNOWN)}.",
        record_id=target.get("ReportID", ""),
        privacy_level=target.get("PrivacyLevel", "private-review"),
        backend_status=result.get("status", "updated"),
    )


def route_task(svc, _svc_cal, fields: dict[str, str], free_text: str, source_link: str, privacy_level: str) -> RouterResult:
    missing = missing_required(fields, ["id", "title"])
    if missing:
        audit_missing(svc, "/task", missing, source_link)
        return RouterResult(False, "/task", "needs_more_info", "Need more info: " + ", ".join(missing), missing_fields=missing)
    result = ops.add_task(
        svc,
        task_id=fields["id"],
        task_title=fields["title"],
        task_description=fields.get("description", free_text or UNKNOWN),
        category=fields.get("category", UNKNOWN),
        priority=fields.get("priority", UNKNOWN),
        assigned_to=fields.get("assigned_to", UNKNOWN),
        due_date=fields.get("due", UNKNOWN),
        status=fields.get("status", "new"),
        source_link=source_link,
    )
    return RouterResult(True, "/task", result.get("status", "written"), "Task row written through backend.", record_id=result["id"], privacy_level=privacy_level, backend_status=result.get("status", "created"))


def route_inventory(svc, _svc_cal, fields: dict[str, str], free_text: str, source_link: str, privacy_level: str) -> RouterResult:
    missing = missing_required(fields, ["id", "item", "quantity"])
    if missing:
        audit_missing(svc, "/inventory", missing, source_link)
        return RouterResult(False, "/inventory", "needs_more_info", "Need more info: " + ", ".join(missing), missing_fields=missing)
    result = ops.update_inventory(
        svc,
        item_id=fields["id"],
        item_name=fields["item"],
        category=fields.get("category", UNKNOWN),
        quantity_on_hand=fields["quantity"],
        unit=fields.get("unit", UNKNOWN),
        minimum_needed=fields.get("minimum", UNKNOWN),
        storage_location=fields.get("storage", "Safe fake storage"),
        condition=fields.get("condition", UNKNOWN),
        notes="Telegram simulated intake; safe fake data only",
    )
    return RouterResult(True, "/inventory", result.get("status", "written"), "Inventory row written through backend.", record_id=result["id"], privacy_level=privacy_level, backend_status=result.get("status", "created"))


def route_event(svc, svc_cal, fields: dict[str, str], free_text: str, source_link: str, privacy_level: str) -> RouterResult:
    missing = missing_required(fields, ["id", "title", "start"])
    if missing:
        audit_missing(svc, "/event", missing, source_link)
        return RouterResult(False, "/event", "needs_more_info", "Need more info: " + ", ".join(missing), missing_fields=missing)
    start = parse_dt(fields["start"])
    if not start:
        audit_missing(svc, "/event", ["start (ISO datetime)"], source_link)
        return RouterResult(False, "/event", "needs_more_info", "Need valid ISO datetime in start=...", missing_fields=["start"])
    end = parse_dt(fields.get("end", "")) or (start + timedelta(hours=1))
    title = f"{fields['id']} — {fields['title']}"
    result = ops.create_calendar_event(
        svc_cal,
        svc,
        event_title=title,
        event_type=fields.get("type", "telegram-test"),
        start_time=start,
        end_time=end,
        description=fields.get("description", free_text or "Safe fake Telegram event"),
        location=fields.get("location", ""),
        private_location="",
        related_task_id=fields.get("task", ""),
        related_request_id=fields.get("request", ""),
        related_donation_id=fields.get("donation", ""),
    )
    return RouterResult(True, "/event", result.get("status", "written"), "Calendar event created through backend.", record_id=fields["id"], calendar_event_id=result.get("calendar_id", ""), privacy_level=privacy_level, backend_status=result.get("status", "created"))


def run_sync() -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, str(SYNC_SCRIPT)],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "sync failed")
    return json.loads(proc.stdout)


def read_json(name: str) -> list[dict[str, Any]]:
    path = DOCS_DATA / name
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _dedupe_by_key(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    """Return items with unique values for the given key, keeping first occurrence."""
    seen = set()
    out = []
    for item in items:
        val = item.get(key, "")
        if val and val not in seen:
            seen.add(val)
            out.append(item)
    return out


def _dedupe_calendar_by_title(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate calendar items by title, keeping first occurrence.
    Does not delete source rows; only affects /daily display.
    """
    seen = set()
    out = []
    for item in items:
        title = (item.get("EventTitle") or "").strip()
        if title and title not in seen:
            seen.add(title)
            out.append(item)
    return out


def _completed_item_summary(entry: dict[str, Any]) -> tuple[str, str] | None:
    target = str(entry.get("TargetItem", ""))
    action = str(entry.get("Action", ""))
    if target.startswith("Donations/"):
        return ("donation", "created" if action == "create" else "updated" if action == "update" else action)
    if target.startswith("Reports/"):
        return ("report", "created" if action == "create" else "updated" if action == "update" else action)
    if target.startswith("Tasks/"):
        return ("task", "created" if action == "create" else "updated" if action == "update" else action)
    if target.startswith("Inventory/"):
        return ("inventory item", "created" if action == "create" else "updated" if action == "update" else action)
    if target.startswith("CalendarLog/"):
        return ("calendar event", "created" if action == "create" else "updated" if action == "update" else action)
    if target.startswith("Requests/"):
        return ("request", "created" if action == "create" else "updated" if action == "update" else action)
    return None


def _format_completed_item_lines(entries: list[dict[str, Any]]) -> list[str]:
    counts: Counter[tuple[str, str]] = Counter()
    order: list[tuple[str, str]] = []
    for entry in entries:
        key = _completed_item_summary(entry)
        if not key:
            continue
        if key not in counts:
            order.append(key)
        counts[key] += 1

    def pluralize(noun: str, count: int) -> str:
        if count == 1:
            return noun
        parts = noun.split()
        parts[-1] = parts[-1] + "s"
        return " ".join(parts)

    lines: list[str] = []
    for noun, action in order:
        count = counts[(noun, action)]
        lines.append(f"- {count} {pluralize(noun, count)} {action}")
    return lines


def run_daily_summary() -> str:
    sync_result = run_sync()
    needs = read_json("approved_needs.json")
    donations = read_json("approved_donations.json")
    reports = read_json("approved_reports.json")
    calendar = read_json("approved_calendar.json")
    board_log = read_json("approved_board_log.json")

    # Deduplicate by primary keys
    needs = _dedupe_by_key(needs, "RequestID")
    donations = _dedupe_by_key(donations, "DonationID")
    reports = _dedupe_by_key(reports, "ReportID")
    calendar = _dedupe_by_key(calendar, "CalendarEventID")
    calendar = _dedupe_calendar_by_title(calendar)

    today = now_utc().strftime("%Y-%m-%d")
    lines = [
        "Daily board-safe summary",
        f"Date: {today}",
        "",
        "Today's calendar:",
    ]
    today_events = [e for e in calendar if str(e.get("StartDateTime", "")).startswith(today)]
    if today_events:
        for e in today_events[:5]:
            lines.append(f"- {e.get('EventTitle', UNKNOWN)} ({e.get('Status', UNKNOWN)})")
    else:
        lines.append("- No board-safe events found for today.")

    lines += ["", "Open urgent requests:"]
    urgent = [n for n in needs if str(n.get("Urgency", "")).lower() in {"urgent", "high"}]
    if urgent:
        for n in urgent[:5]:
            lines.append(f"- {n.get('RequestID', UNKNOWN)}: {n.get('NeedDescription', UNKNOWN)}")
    else:
        lines.append("- No urgent board-safe requests found.")

    lines += ["", "Donation pickups/drop-offs:"]
    if donations:
        for d in donations[-5:]:
            lines.append(f"- {d.get('DonationID', UNKNOWN)}: {d.get('ItemDescription', UNKNOWN)} ({d.get('Status', UNKNOWN)})")
    else:
        lines.append("- No board-safe donation records found.")

    lines += ["", "Volunteer gaps:", "- None listed in approved-safe export."]
    lines += ["", "Inventory shortages:", "- Inventory is not exported publicly yet; check private Sheet."]
    lines += ["", "Website drafts needing approval:", "- None listed in approved-safe export."]
    lines += ["", "Follow-ups due:"]
    if needs:
        for n in needs[-5:]:
            lines.append(f"- {n.get('RequestID', UNKNOWN)} next action: {n.get('NextAction', UNKNOWN)}")
    else:
        lines.append("- No follow-ups listed.")
    lines += ["", "Sensitive items requiring human review:", "- Not exported to docs/. Check private systems only if needed."]
    lines += ["", "Completed items since last brief:"]
    visible_request_ids = {n.get("RequestID") for n in needs if n.get("RequestID")}
    recent_success = []
    for a in [x for x in board_log if x.get("Result") == "success"]:
        target = str(a.get("TargetItem", ""))
        if target.startswith("Requests/") and target.split("/", 1)[1] in visible_request_ids:
            continue
        recent_success.append(a)
    recent_success = recent_success[-50:]
    if recent_success:
        lines.extend(_format_completed_item_lines(recent_success))
    else:
        lines.append("- No recent successful audit entries found.")
    lines += ["", "Website:", "- Board home: https://falloutmule.github.io/non-profit-hermes-mvp/", "- Today: https://falloutmule.github.io/non-profit-hermes-mvp/today.html", "- Current needs: https://falloutmule.github.io/non-profit-hermes-mvp/current-needs.html", "- Calendar: https://falloutmule.github.io/non-profit-hermes-mvp/calendar.html", "- Reports: https://falloutmule.github.io/non-profit-hermes-mvp/reports.html"]
    lines += ["", "Sync state:", f"- Marker: {sync_result.get('marker', UNKNOWN)}", f"- Rows: {sync_result.get('rows', {})}"]
    lines += ["", "daily_plugin_version: website-links-dedup-003"]
    return "\n".join(lines)


def safe_test_messages() -> list[str]:
    start = (now_utc() + timedelta(hours=4)).replace(microsecond=0)
    end = start + timedelta(hours=1)
    return [
        '/need id=REQ-TG-TEST-001 category=clothing description="Safe fake Telegram need for blankets" quantity=2 urgency=low needed_by=2099-01-01 next_action=review',
        '/donation id=DON-TG-TEST-001 type=clothing item="Safe fake Telegram donation of coats" quantity=3 condition=new method=dropoff location="Safe fake public dropoff" available=2099-01-01',
        '/report type=test summary="Safe fake Telegram report summary"',
        '/task id=TASK-TG-TEST-001 title="Safe fake Telegram task" description="Verify Telegram router task write" category=test priority=low due=2099-01-01 assigned_to=unknown',
        '/inventory id=INV-TG-TEST-001 item="Safe fake Telegram socks" category=socks quantity=42 unit=pairs minimum=10 storage="Safe fake storage shelf" condition=new',
        f'/event id=CAL-TG-TEST-001 title="Safe fake Telegram calendar event" start={start.isoformat()} end={end.isoformat()} type=telegram-test request=REQ-TG-TEST-001 task=TASK-TG-TEST-001',
        '/daily',
        '/need id=REQ-TG-HOLD-001 description="medical private-location camp test should hold"',
        '/need id=REQ-TG-MISSING-001',
        '/report pantry gave out socks and toilet paper',
    ]



def report_followup_test_sequence() -> list[tuple[str, str]]:
    """Conversation-style test for active /report draft follow-up handling."""
    source = "telegram-simulated:report-followup"
    return [
        (source, '/report pantry gave out socks and toilet paper'),
        (source, 'report_type=pantry date=today people_served_estimate=unknown items_distributed="socks and toilet paper" followups_needed=none privacy_level=board-visible public_summary_allowed=yes status=ready next_action=review'),
    ]


def need_followup_test_sequence() -> list[tuple[str, str]]:
    """Conversation-style test for active /need draft follow-up handling."""
    source = "telegram-simulated:need-followup"
    return [
        (source, '/need 6 rolls of toilet paper'),
        (source, 'urgency=normal needed_by=unknown location="public-safe test area" privacy_level=board-visible status=ready'),
    ]


def run_test() -> int:
    print("=== Non-Profit Hermes Telegram Intake Router — Safe Test ===")
    results: list[dict[str, Any]] = []
    for i, message in enumerate(safe_test_messages(), start=1):
        source = f"{SOURCE_PREFIX}:{i}"
        result = handle_message(message, source_link=source)
        results.append({"input": message, "result": result.to_dict()})
        print(f"\n[{i}] {message.split()[0]} → {result.status}")
        print(result.message)
        if result.record_id:
            print(f"record_id: {result.record_id}")
        if result.calendar_event_id:
            print(f"calendar_event_id: {result.calendar_event_id}")
        if result.summary:
            print(result.summary)

    print("\n=== Conversation follow-up test ===\n")

    print("--- Report follow-up ---")
    for i, (source, message) in enumerate(report_followup_test_sequence(), start=1):
        result = handle_message(message, source_link=source)
        results.append({"input": message, "source": source, "result": result.to_dict()})
        print(f"\n[RF{i}] {message.split()[0] if message.startswith('/') else message[:50]} → {result.status}")
        print(result.message)
        if result.record_id:
            print(f"record_id: {result.record_id}")

    print("\n--- Need follow-up ---")
    for i, (source, message) in enumerate(need_followup_test_sequence(), start=1):
        result = handle_message(message, source_link=source)
        results.append({"input": message, "source": source, "result": result.to_dict()})
        print(f"\n[F{i}] {message.split()[0]} → {result.status}")
        print(result.message)
        if result.record_id:
            print(f"record_id: {result.record_id}")

    print("\n=== JSON result ===")
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Safe Telegram intake router for Non-Profit Hermes")
    parser.add_argument("--test", action="store_true", help="Run safe fake Telegram intake simulation")
    parser.add_argument("--message", help="Route one command-like Telegram message")
    args = parser.parse_args()

    if args.test:
        return run_test()
    if args.message:
        result = handle_message(args.message)
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        if result.summary:
            print("\n" + result.summary)
        return 0 if result.ok else 2

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
