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
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(r"C:\Users\fallo\non-profit-hermes-mvp")
SCRIPTS = ROOT / "scripts"
DOCS_DATA = ROOT / "docs" / "data"
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


def _result_to_text(result: "RouterResult") -> str:
    """Render a RouterResult as a board-safe Telegram reply."""
    if result.summary:
        # /daily returns the full summary; pass it through unchanged.
        return result.summary
    if not result.ok and result.status == "needs_more_info":
        return (
            f"Need more info to create this request.\n"
            f"Missing: {', '.join(result.missing_fields)}\n\n"
            f"Example:\n"
            f"/need id=REQ-EXAMPLE-001 description=\"Short safe need\" urgency=normal needed_by=unknown location=\"public-safe area\" privacy_level=board-visible next_action=review"
        )
    if not result.ok and result.sensitive_hold:
        return result.message
    if result.ok and result.backend_status == "already_exists":
        return f"Request {result.record_id} already exists; duplicate skipped (no new row written)."
    if result.ok and result.status in {"needs-info", "draft"}:
        missing = ", ".join(result.missing_fields or []) or "none"
        return (
            f"Draft request created: {result.record_id}\n"
            f"Privacy: {result.privacy_level}\n"
            f"Status: {result.status}\n"
            f"Missing: {missing}\n"
            f"Next action: review"
        )
    if result.ok:
        return (
            f"Request created: {result.record_id}\n"
            f"Privacy: {result.privacy_level}\n"
            f"Status: {result.backend_status}\n"
            f"Run /daily to see board summary, or visit the Current Needs page."
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


def services():
    c = ops.get_creds()
    return ops.sheets(c), ops.calendar(c)


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


def route_donation(svc, _svc_cal, fields: dict[str, str], free_text: str, source_link: str, privacy_level: str) -> RouterResult:
    missing = missing_required(fields, ["id", "item"])
    if missing:
        audit_missing(svc, "/donation", missing, source_link)
        return RouterResult(False, "/donation", "needs_more_info", "Need more info: " + ", ".join(missing), missing_fields=missing)
    result = ops.add_donation(
        svc,
        donation_id=fields["id"],
        donor_name=fields.get("donor_name", "Safe fake donor"),
        donor_contact=UNKNOWN,
        donation_type=fields.get("type", UNKNOWN),
        item_description=fields["item"] or free_text or UNKNOWN,
        quantity=fields.get("quantity", UNKNOWN),
        condition=fields.get("condition", UNKNOWN),
        pickup_or_dropoff=fields.get("method", UNKNOWN),
        location=fields.get("location", "Safe fake public location"),
        available_date=fields.get("available", UNKNOWN),
        status=fields.get("status", "new"),
        source_link=source_link,
    )
    return RouterResult(True, "/donation", result.get("status", "written"), "Donation row written through backend.", record_id=result["id"], privacy_level=privacy_level, backend_status=result.get("status", "created"))


def route_report(svc, _svc_cal, fields: dict[str, str], free_text: str, source_link: str, privacy_level: str) -> RouterResult:
    missing = missing_required(fields, ["id", "summary"])
    if missing:
        audit_missing(svc, "/report", missing, source_link)
        return RouterResult(False, "/report", "needs_more_info", "Need more info: " + ", ".join(missing), missing_fields=missing)
    result = ops.add_report(
        svc,
        report_id=fields["id"],
        submitted_by=fields.get("submitted_by", "Telegram user (safe fake)"),
        report_type=fields.get("type", "test"),
        summary=fields["summary"] or free_text or UNKNOWN,
        privacy_level=privacy_level,
        sensitive_details="",
        source_link=source_link,
    )
    return RouterResult(True, "/report", result.get("status", "written"), "Report row written through backend.", record_id=result["id"], privacy_level=privacy_level, backend_status=result.get("status", "created"))


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
        if target.startswith("Requests/") and target.split("/", 1)[1] not in visible_request_ids:
            continue
        recent_success.append(a)
    recent_success = recent_success[-5:]
    if recent_success:
        for a in recent_success:
            lines.append(f"- {a.get('Action', UNKNOWN)} {a.get('TargetItem', UNKNOWN)}")
    else:
        lines.append("- No recent successful audit entries found.")
    lines += ["", "Website:", "- Board home: https://falloutmule.github.io/non-profit-hermes-mvp/", "- Today: https://falloutmule.github.io/non-profit-hermes-mvp/today.html", "- Current needs: https://falloutmule.github.io/non-profit-hermes-mvp/current-needs.html", "- Calendar: https://falloutmule.github.io/non-profit-hermes-mvp/calendar.html", "- Reports: https://falloutmule.github.io/non-profit-hermes-mvp/reports.html"]
    lines += ["", "Sync state:", f"- Marker: {sync_result.get('marker', UNKNOWN)}", f"- Rows: {sync_result.get('rows', {})}"]
    lines += ["", "daily_plugin_version: website-links-dedup-002"]
    return "\n".join(lines)


def safe_test_messages() -> list[str]:
    start = (now_utc() + timedelta(hours=4)).replace(microsecond=0)
    end = start + timedelta(hours=1)
    return [
        '/need id=REQ-TG-TEST-001 category=clothing description="Safe fake Telegram need for blankets" quantity=2 urgency=low needed_by=2099-01-01 next_action=review',
        '/donation id=DON-TG-TEST-001 type=clothing item="Safe fake Telegram donation of coats" quantity=3 condition=new method=dropoff location="Safe fake public dropoff" available=2099-01-01',
        '/report id=REP-TG-TEST-001 type=test summary="Safe fake Telegram report summary"',
        '/task id=TASK-TG-TEST-001 title="Safe fake Telegram task" description="Verify Telegram router task write" category=test priority=low due=2099-01-01 assigned_to=unknown',
        '/inventory id=INV-TG-TEST-001 item="Safe fake Telegram socks" category=socks quantity=42 unit=pairs minimum=10 storage="Safe fake storage shelf" condition=new',
        f'/event id=CAL-TG-TEST-001 title="Safe fake Telegram calendar event" start={start.isoformat()} end={end.isoformat()} type=telegram-test request=REQ-TG-TEST-001 task=TASK-TG-TEST-001',
        '/daily',
        '/need id=REQ-TG-HOLD-001 description="medical private-location camp test should hold"',
        '/need id=REQ-TG-MISSING-001',
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
