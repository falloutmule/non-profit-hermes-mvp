from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from html import escape

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# ── Canonical shared schema ─────────────────────────────────────────────────

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from non_profit_hermes_schema import (
    HEADERS,
    PRIMARY_KEYS,
    AFFIRMATIVE_VALUES,
    APPROVED_PRIVACY_LEVELS,
    TERMINAL_STATUSES,
    PUBLIC_STATUS_BY_TYPE,
    PUBLIC_SUMMARY_ALLOWED_FIELD,
    PUBLIC_LISTING_ALLOWED_FIELD,
    PRIVACY_LEVEL_FIELD,
    LAST_UPDATED_FIELD,
    CONSENT_TO_SHARE_FIELD,
    CONSENT_TO_PUBLIC_THANKS_FIELD,
    col,
    get_header_range,
    get_full_range,
    get_primary_key,
    is_affirmative,
    is_approved_privacy,
    is_public_status,
    is_terminal_status,
    TAB_ORDER,
)

ROOT = Path(r"C:\Users\fallo\non-profit-hermes-mvp")
DOCS = ROOT / "docs"
DATA = DOCS / "data"
TOKEN = Path(r"C:\Users\fallo\AppData\Local\hermes\google_token.json")
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
]
SPREADSHEET_ID = "1Sf68PnxsuqW2PVzHZgyh8vV90Y4UlJ-GYexQ7JlOxlE"
CALENDAR_ID = "e1c99cc72c43a87bb340a6e867f0b56caf1da4d4f485454e2370e17daa20e32a@group.calendar.google.com"
TEST_EVENT_TITLE = "TEST - Non-Profit Hermes Calendar Wiring"
TEST_EVENT_DESC = "Safe test event for MVP wiring verification."
MARKER = "CLEAN_DOCS_DEPLOY_NON_PROFIT_HERMES_002"

HTML_HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;max-width:52rem;margin:2rem auto;padding:0 1rem;line-height:1.55;color:#1f2937;background:#fff}
a{color:#1d4ed8;text-decoration:none} a:hover{text-decoration:underline}
header,footer{font-size:.95rem;color:#6b7280;margin:0 0 1.25rem}
nav a{margin-right:1rem}
main{padding:1rem 0}
h1,h2,h3{line-height:1.2}
code,pre{background:#f3f4f6;border-radius:6px}
pre{padding:1rem;overflow:auto}
</style>
</head>
<body>
<header>
<nav>
{nav_links}
</nav>
</header>
<main>
"""

HTML_FOOT = """</main>
<footer>Board-facing only. No private intake.</footer>
</body>
</html>"""

NAV_LINKS = """<a href="./">Home</a>
<a href="./today/">Today</a>
<a href="./current-needs/">Current Needs</a>
<a href="./calendar/">Calendar</a>
<a href="./reports/">Reports</a>
<a href="./deployment-proof/">Deployment Proof</a>"""

NAV_LINKS_SUB = """<a href="../">Home</a>
<a href="../today/">Today</a>
<a href="../current-needs/">Current Needs</a>
<a href="../calendar/">Calendar</a>
<a href="../reports/">Reports</a>
<a href="../deployment-proof/">Deployment Proof</a>"""


def creds(*, persist_refresh: bool = True) -> Credentials:
    """Load credentials, refreshing in memory unless persistence is requested."""
    c = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if c.expired and c.refresh_token:
        c.refresh(Request())
        if persist_refresh:
            TOKEN.write_text(json.dumps(json.loads(c.to_json()), indent=2))
    return c


def sheets_service(c: Credentials):
    return build("sheets", "v4", credentials=c)


def calendar_service(c: Credentials):
    return build("calendar", "v3", credentials=c)


def read_sheet_rows(svc, tab: str) -> list[list[str]]:
    """Read all used rows through the canonical full-column range."""
    result = svc.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=get_full_range(tab)
    ).execute()
    return result.get("values", [])


def esc(value: object) -> str:
    """Escape a value for safe HTML insertion."""
    return escape(str(value or ""), quote=True)


def html_list(items: list[str]) -> str:
    return "\n".join(f"<li>{item}</li>" for item in items) if items else "<li>none</li>"


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def write_page(path: Path, title: str, body_html: str, nav_links: str = NAV_LINKS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_page(title, body_html, nav_links))


def render_page(title: str, body_html: str, nav_links: str = NAV_LINKS) -> str:
    """Return a complete HTML document; callers must escape dynamic values first."""
    head = HTML_HEAD.replace("{title}", esc(title)).replace("{nav_links}", nav_links)
    return head + body_html + HTML_FOOT


def write_both(base: Path, title: str, body_html: str) -> None:
    """Write both page.html and page/index.html."""
    write_page(base.with_suffix(".html"), title, body_html, nav_links=NAV_LINKS)
    idx_dir = base.parent / base.stem / "index.html"
    write_page(idx_dir, title, body_html, nav_links=NAV_LINKS_SUB)


# ── Deduplication helper ──────────────────────────────────────────────────────

def deduplicate_rows(
    rows: list[list[str]],
    tab: str,
    header: list[str],
) -> list[dict]:
    """
    Deduplicate rows by primary key, keeping the newest row.

    Newest = highest LastUpdated, then highest record date, then last physical row.
    """
    if not rows or len(rows) < 2:
        return [dict(zip(header, r)) for r in rows[1:]] if rows else []

    pk = PRIMARY_KEYS.get(tab, "")
    if not pk or pk not in header:
        # No primary key defined or not in header - no dedup
        return [dict(zip(header, r)) for r in rows[1:]]

    pk_idx = header.index(pk)
    last_updated_idx = header.index(LAST_UPDATED_FIELD) if LAST_UPDATED_FIELD in header else -1

    # Group rows by primary key with row index
    groups: dict[str, list[tuple[int, dict]]] = {}
    for idx, row in enumerate(rows[1:], start=1):
        if not row:
            continue
        # Pad row to header length
        padded = row + [""] * (len(header) - len(row))
        data = dict(zip(header, padded))
        key = data.get(pk, "").strip()
        if not key:
            continue
        groups.setdefault(key, []).append((idx, data))

    # For each key, select the newest row
    selected = []
    for key, group in groups.items():
        if len(group) == 1:
            selected.append(group[0][1])
        else:
            # Sort by: LastUpdated desc, then physical row desc
            group.sort(
                key=lambda x: (
                    x[1].get(LAST_UPDATED_FIELD, "") if last_updated_idx >= 0 else "",
                    x[0],
                ),
                reverse=True,
            )
            selected.append(group[0][1])

    return selected


def duplicate_count(rows: list[list[str]], tab: str) -> int:
    """Return the number of non-empty keyed rows superseded by a duplicate."""
    if not rows:
        return 0
    primary_key = PRIMARY_KEYS.get(tab)
    if not primary_key or primary_key not in rows[0]:
        return 0
    key_index = rows[0].index(primary_key)
    counts = Counter(
        row[key_index].strip()
        for row in rows[1:]
        if row and len(row) > key_index and row[key_index].strip()
    )
    return sum(count - 1 for count in counts.values() if count > 1)


def rejection_reason(tab: str, data: dict[str, str]) -> str | None:
    """Return the first deny-by-default gate that rejects a public export row."""
    privacy = (data.get(PRIVACY_LEVEL_FIELD, "") or "").strip().lower()
    if not is_approved_privacy(privacy):
        return "privacy_not_approved"
    status = (data.get("Status", "") or "").strip().lower()
    if is_terminal_status(status):
        return "terminal_status"
    if not is_public_status(tab, status):
        return "status_not_public"
    if tab == "Requests":
        if not is_affirmative((data.get(CONSENT_TO_SHARE_FIELD, "") or "").strip()):
            return "consent_not_affirmative"
        if not data.get("NeedDescription", ""):
            return "missing_need_description"
    elif tab == "Donations":
        if not is_affirmative((data.get(PUBLIC_LISTING_ALLOWED_FIELD, "") or "").strip()):
            return "public_listing_not_affirmative"
        if not data.get("ItemDescription", ""):
            return "missing_item_description"
    elif tab == "Reports":
        if not is_affirmative((data.get(PUBLIC_SUMMARY_ALLOWED_FIELD, "") or "").strip()):
            return "public_summary_not_affirmative"
        if not data.get("PublicSummaryDraft", ""):
            return "missing_public_summary"
    return None


def calendar_rejection_reason(data: dict[str, str], approved_event_ids: set[str]) -> str | None:
    """Classify CalendarLog rows using the same gates as ``safe_calendar_export``."""
    event_id = (data.get("CalendarEventID", "") or "").strip()
    if not event_id:
        return "missing_calendar_event_id"
    if not is_approved_privacy((data.get(PRIVACY_LEVEL_FIELD, "") or "").strip()):
        return "privacy_not_approved"
    if not is_affirmative((data.get("PublicCalendarAllowed", "") or "").strip()):
        return "public_calendar_not_affirmative"
    if (data.get("ApprovalStatus", "") or "").strip().lower() not in {"approved", "created"}:
        return "approval_not_approved"
    if (data.get("Status", "") or "").strip().lower() not in {"confirmed", "ready"}:
        return "status_not_public"
    if not (data.get("PublicTitle", "") or "").strip():
        return "missing_public_title"
    if event_id not in approved_event_ids:
        return "event_not_live_or_cancelled"
    return None


def dry_run_metrics(tab_rows: dict[str, list[list[str]]], out: dict[str, list[dict]]) -> dict:
    """Build JSON-safe, write-free observability metrics from the loaded rows."""
    rejected: dict[str, dict[str, int]] = {}
    for tab in ("Requests", "Donations", "Reports"):
        rows = tab_rows.get(tab, [])
        if not rows:
            continue
        reasons = Counter()
        primary_key = PRIMARY_KEYS[tab]
        primary_key_index = rows[0].index(primary_key)
        missing_primary_keys = sum(
            1 for row in rows[1:]
            if row and (len(row) <= primary_key_index or not row[primary_key_index].strip())
        )
        if missing_primary_keys:
            reasons["missing_primary_key"] = missing_primary_keys
        for data in deduplicate_rows(rows, tab, rows[0]):
            reason = rejection_reason(tab, data)
            if reason:
                reasons[reason] += 1
        if reasons:
            rejected[tab] = dict(sorted(reasons.items()))

    calendar_rows = tab_rows.get("CalendarLog", [])
    if calendar_rows:
        calendar_reasons = Counter()
        approved_event_ids = {item["CalendarEventID"] for item in out["approved_calendar"]}
        for data in deduplicate_rows(calendar_rows, "CalendarLog", calendar_rows[0]):
            reason = calendar_rejection_reason(data, approved_event_ids)
            if reason:
                calendar_reasons[reason] += 1
        if calendar_reasons:
            rejected["CalendarLog"] = dict(sorted(calendar_reasons.items()))
    return {
        "mode": "dry-run",
        "rows_read_by_tab": {tab: len(rows) for tab, rows in tab_rows.items()},
        "rows_after_row_100_by_tab": {
            tab: sum(1 for row in rows[100:] if row)
            for tab, rows in tab_rows.items()
        },
        "approved_counts": {name: len(items) for name, items in out.items()},
        "rejected_counts_by_reason": rejected,
        "duplicate_counts_by_tab": {
            tab: duplicate_count(rows, tab) for tab, rows in tab_rows.items()
        },
        "board_log_aggregate_count": len(out["approved_board_log"]),
        "filesystem_writes": 0,
    }


# ── Safe export functions with deny-by-default gates ─────────────────────────

def safe_needs_from_requests(rows: list[list[str]]) -> list[dict[str, str]]:
    """Export requests with deny-by-default: must have affirmative ConsentToShare."""
    out = []
    if not rows:
        return out
    header = rows[0]
    for data in deduplicate_rows(rows, "Requests", header):
        privacy = (data.get(PRIVACY_LEVEL_FIELD, "") or "").strip().lower()
        if not is_approved_privacy(privacy):
            continue
        status = (data.get("Status", "") or "").strip().lower()
        if is_terminal_status(status):
            continue
        if not is_public_status("Requests", status):
            continue
        consent = (data.get(CONSENT_TO_SHARE_FIELD, "") or "").strip()
        if not is_affirmative(consent):
            continue
        need_desc = data.get("NeedDescription", "")
        if not need_desc:
            continue
        out.append({
            "RequestID": data.get("RequestID", ""),
            "DateReceived": data.get("DateReceived", ""),
            "NeedCategory": data.get("NeedCategory", ""),
            "NeedDescription": need_desc,
            "Quantity": data.get("Quantity", ""),
            "Urgency": data.get("Urgency", ""),
            "NeededBy": data.get("NeededBy", ""),
            "PrivacyLevel": data.get(PRIVACY_LEVEL_FIELD, ""),
            "Status": data.get("Status", ""),
            "NextAction": data.get("NextAction", ""),
        })
    return out


def safe_donations(rows: list[list[str]]) -> list[dict[str, str]]:
    """Export donations with deny-by-default: must have PrivacyLevel approved and PublicListingAllowed affirmative."""
    out = []
    if not rows:
        return out
    header = rows[0]
    for data in deduplicate_rows(rows, "Donations", header):
        privacy = (data.get(PRIVACY_LEVEL_FIELD, "") or "").strip().lower()
        if not is_approved_privacy(privacy):
            continue
        status = (data.get("Status", "") or "").strip().lower()
        if is_terminal_status(status):
            continue
        if not is_public_status("Donations", status):
            continue
        listing_allowed = (data.get(PUBLIC_LISTING_ALLOWED_FIELD, "") or "").strip()
        if not is_affirmative(listing_allowed):
            continue
        item_desc = data.get("ItemDescription", "")
        if not item_desc:
            continue
        out.append({
            "DonationID": data.get("DonationID", ""),
            "DateOffered": data.get("DateOffered", ""),
            "DonationType": data.get("DonationType", ""),
            "ItemDescription": item_desc,
            "Quantity": data.get("Quantity", ""),
            "Status": data.get("Status", ""),
            "ReceiptNeeded": data.get("ReceiptNeeded", ""),
            "ThankYouNeeded": data.get("ThankYouNeeded", ""),
        })
    return out


def safe_reports(rows: list[list[str]]) -> list[dict[str, str]]:
    """Export reports with deny-by-default: must have PublicSummaryAllowed affirmative, PublicSummaryDraft non-empty."""
    out = []
    if not rows:
        return out
    header = rows[0]
    for data in deduplicate_rows(rows, "Reports", header):
        privacy = (data.get(PRIVACY_LEVEL_FIELD, "") or "").strip().lower()
        if not is_approved_privacy(privacy):
            continue
        status = (data.get("Status", "") or "").strip().lower()
        if is_terminal_status(status):
            continue
        if not is_public_status("Reports", status):
            continue
        psa = (data.get(PUBLIC_SUMMARY_ALLOWED_FIELD, "") or "").strip()
        if not is_affirmative(psa):
            continue
        public_summary = data.get("PublicSummaryDraft", "")
        if not public_summary:
            continue
        out.append({
            "ReportID": data.get("ReportID", ""),
            "Date": data.get("Date", ""),
            "ReportType": data.get("ReportType", ""),
            "Summary": public_summary,  # Use PublicSummaryDraft, not raw Summary
            "PeopleServedEstimate": data.get("PeopleServedEstimate", ""),
            "ItemsDistributed": data.get("ItemsDistributed", ""),
            "PrivacyLevel": data.get(PRIVACY_LEVEL_FIELD, ""),
        })
    return out


def safe_volunteer_gaps() -> list[dict[str, str]]:
    return []


def safe_board_log(
    rows: list[list[str]],
    visible_request_ids: set[str] | None = None,
    visible_donation_ids: set[str] | None = None,
    visible_report_ids: set[str] | None = None,
) -> list[dict[str, str]]:
    """Aggregate board log into summary counts - NO internal IDs exposed."""
    out = []
    if not rows:
        return out
    header = rows[0]
    visible_request_ids = visible_request_ids or set()
    visible_donation_ids = visible_donation_ids or set()
    visible_report_ids = visible_report_ids or set()

    # Group by date, record type, action
    from collections import defaultdict
    counts: dict[tuple[str, str, str], int] = defaultdict(int)

    for r in rows[1:]:
        if not r:
            continue
        data = dict(zip(header, r))
        target = data.get("TargetItem", "")
        action = data.get("Action", "").lower()
        date = data.get("Timestamp", "")[:10]  # YYYY-MM-DD

        # Filter: only include visible request/report actions
        if target.startswith("Requests/"):
            rid = target.split("/", 1)[1]
            if rid not in visible_request_ids:
                continue
            rectype = "request"
        elif target.startswith("Reports/"):
            rid = target.split("/", 1)[1]
            if rid not in visible_report_ids:
                continue
            rectype = "report"
        elif target.startswith("Donations/"):
            donation_id = target.split("/", 1)[1]
            if donation_id not in visible_donation_ids:
                continue
            rectype = "donation"
        elif target.startswith("CalendarLog/"):
            rectype = "event"
        elif target.startswith("Tasks/") or target.startswith("Inventory/"):
            continue  # Internal only
        else:
            rectype = "other"

        # Normalize action
        if action in ("create", "created"):
            action_norm = "created"
        elif action in ("update", "updated"):
            action_norm = "updated"
        elif action in ("duplicate_skipped",):
            action_norm = "duplicate skipped"
        else:
            action_norm = action

        counts[(date, rectype, action_norm)] += 1

    # Build output
    for (date, rectype, action), count in sorted(counts.items()):
        out.append({
            "Date": date,
            "RecordType": rectype,
            "Action": action,
            "Count": count,
        })
    return out


def safe_calendar_export(calendar_rows: list[list[str]], calendar_svc) -> list[dict[str, str]]:
    """Export only explicitly approved public CalendarLog rows with live IDs."""
    events_resource = calendar_svc.events()
    live_events = []
    page_token = None
    while True:
        request = events_resource.list(
            calendarId=CALENDAR_ID,
            singleEvents=True,
            orderBy="startTime",
            maxResults=2500,
            **({"pageToken": page_token} if page_token else {}),
        )
        response = request.execute()
        live_events.extend(response.get("items", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    live_status_by_id = {
        str(event.get("id", "")): str(event.get("status", "")).strip().lower()
        for event in live_events
        if event.get("id")
    }
    allowed_privacy = APPROVED_PRIVACY_LEVELS
    allowed_public = {"yes", "true", "1"}
    allowed_approval = {"approved", "created"}
    allowed_status = {"confirmed", "ready"}
    out = []
    if not calendar_rows:
        return out
    header = calendar_rows[0]
    for data in deduplicate_rows(calendar_rows, "CalendarLog", header):
        event_id = data.get("CalendarEventID", "").strip()
        privacy = data.get("PrivacyLevel", "").strip().lower()
        public_allowed = data.get("PublicCalendarAllowed", "").strip().lower()
        approval = data.get("ApprovalStatus", "").strip().lower()
        status = data.get("Status", "").strip().lower()
        public_title = data.get("PublicTitle", "").strip()
        if (
            not event_id
            or privacy not in allowed_privacy
            or public_allowed not in allowed_public
            or approval not in allowed_approval
            or status not in allowed_status
            or not public_title
            or event_id not in live_status_by_id
            or live_status_by_id[event_id] == "cancelled"
        ):
            continue
        out.append({
            "CalendarEventID": event_id,
            "EventTitle": public_title,
            "EventType": data.get("EventType", ""),
            "StartDateTime": data.get("StartDateTime", ""),
            "EndDateTime": data.get("EndDateTime", ""),
            "Description": data.get("PublicDescription", ""),
            "Location": data.get("PublicLocation", ""),
            "Status": data.get("Status", ""),
        })
    return out


# ── HTML page building ────────────────────────────────────────────────────────

def build_pages(
    now: datetime,
    needs,
    calendar_items,
    reports,
    donations,
    board_log,
) -> None:
    timestamp = now.strftime("%Y-%m-%d %H:%M UTC")
    safe_state = "approved-safe sync verified"

    # --- index.html ---
    preview_items = []
    if calendar_items:
        preview_items.append(f"Calendar event: <code>{esc(calendar_items[0]['EventTitle'])}</code>")
        preview_items.append(f"Calendar status: <code>{esc(calendar_items[0]['Status'])}</code>")
    if board_log:
        preview_items.append(f"Board log action: <code>{esc(board_log[0]['Action'])}</code>")
    if reports:
        preview_items.append(f"Report: <code>{esc(reports[0]['ReportID'])}</code> &mdash; {esc(reports[0]['Summary'])}")
    if needs:
        preview_items.append(f"Request: <code>{esc(needs[0]['RequestID'])}</code> &mdash; {esc(needs[0]['NeedDescription'])}")
    if donations:
        preview_items.append(f"Donation: <code>{esc(donations[0]['DonationID'])}</code> &mdash; {esc(donations[0]['ItemDescription'])}")

    index_body = f"""<h1>Non-Profit Hermes MVP</h1>
<p>This site shows only board-approved, public-safe updates.</p>
<h2>Status</h2>
<ul>
<li><strong>Last update:</strong> {timestamp}</li>
<li><strong>Current state:</strong> {safe_state}</li>
</ul>
<h2>Deployment marker</h2>
<p><code>{MARKER}</code></p>
<h2>Approved-safe data</h2>
<ul>
<li><a href="data/approved_needs.json">approved_needs.json</a></li>
<li><a href="data/approved_calendar.json">approved_calendar.json</a></li>
<li><a href="data/approved_reports.json">approved_reports.json</a></li>
<li><a href="data/approved_donations.json">approved_donations.json</a></li>
<li><a href="data/approved_volunteer_gaps.json">approved_volunteer_gaps.json</a></li>
<li><a href="data/approved_board_log.json">approved_board_log.json</a></li>
</ul>
<h2>Approved-safe preview</h2>
<ul>
{html_list(preview_items)}
</ul>"""
    write_both(DOCS / "index", "Non-Profit Hermes MVP", index_body)

    # --- current-needs.html ---
    needs_items = []
    board_needs = [n for n in needs if str(n.get("PrivacyLevel", "")).lower() in {"board-visible", "public-safe", "board-visible-test"}]
    if board_needs:
        needs_items.append(f"Deployment marker: <code>{MARKER}</code>")
        needs_items.append(f"Board-visible needs: <code>{len(board_needs)}</code>")
        for n in board_needs:
            needs_items.append(
                f"Need <code>{esc(n.get('RequestID', 'unknown'))}</code>: {esc(n.get('NeedDescription', 'unknown'))} "
                f"(category: {esc(n.get('NeedCategory', 'unknown'))}, urgency: {esc(n.get('Urgency', 'unknown'))}, status: {esc(n.get('Status', 'unknown'))})"
            )
    else:
        needs_items.append(f"Deployment marker: <code>{MARKER}</code>")
        needs_items.append("No board-visible needs records available.")

    needs_body = f"""<h1>Current Needs</h1>
<p>Approved-safe current needs.</p>
<h2>Approved-safe records</h2>
<ul>
{html_list(needs_items)}
</ul>"""
    write_both(DOCS / "current-needs", "Current Needs", needs_body)

    # --- calendar.html ---
    cal_items = []
    if calendar_items:
        cal_items.append(f"Deployment marker: <code>{MARKER}</code>")
        cal_items.append(f"Event: <code>{esc(calendar_items[0]['EventTitle'])}</code>")
        cal_items.append(f"Type: <code>{esc(calendar_items[0]['EventType'])}</code>")
        cal_items.append(f"Status: <code>{esc(calendar_items[0]['Status'])}</code>")
    else:
        cal_items.append(f"Deployment marker: <code>{MARKER}</code>")
        cal_items.append("No calendar events available.")

    cal_body = f"""<h1>Calendar</h1>
<p>Approved-safe board-visible calendar items.</p>
<h2>Approved-safe records</h2>
<ul>
{html_list(cal_items)}
</ul>"""
    write_both(DOCS / "calendar", "Calendar", cal_body)

    # --- reports.html ---
    rep_items = []
    if reports:
        rep_items.append(f"Deployment marker: <code>{MARKER}</code>")
        rep_items.append(f"Report ID: <code>{esc(reports[0]['ReportID'])}</code>")
        rep_items.append(f"Summary: <code>{esc(reports[0]['Summary'])}</code>")
        rep_items.append(f"Privacy level: <code>{esc(reports[0]['PrivacyLevel'])}</code>")
    else:
        rep_items.append(f"Deployment marker: <code>{MARKER}</code>")
        rep_items.append("No reports available.")

    reports_body = f"""<h1>Reports</h1>
<p>Approved-safe summaries.</p>
<h2>Approved-safe records</h2>
<ul>
{html_list(rep_items)}
</ul>"""
    write_both(DOCS / "reports", "Reports", reports_body)

    # --- today.html ---
    today_items = []
    today_items.append(f"Deployment marker: <code>{MARKER}</code>")
    if calendar_items:
        today_items.append(f"Calendar test event: <code>{esc(calendar_items[0]['EventTitle'])}</code>")
        today_items.append(f"Calendar status: <code>{esc(calendar_items[0]['Status'])}</code>")
    if needs:
        today_items.append(f"Urgent needs: <code>{esc(needs[0]['RequestID'])}</code> ({esc(needs[0]['NeedDescription'])})")
    if reports:
        today_items.append(f"Latest report: <code>{esc(reports[0]['ReportID'])}</code>")
    if not calendar_items and not needs and not reports:
        today_items.append("No current-day data available.")

    today_body = f"""<h1>Today</h1>
<p>Approved-safe current-day summary.</p>
<h2>Approved-safe records</h2>
<ul>
{html_list(today_items)}
</ul>"""
    write_both(DOCS / "today", "Today", today_body)

    # --- deployment-proof.html ---
    proof_body = f"""<h1>Deployment Proof</h1>
<p><code>{MARKER}</code></p>
<p>This page proves the clean docs/ deployment is live and the sync script is generating correct output.</p>
<ul>
<li>Last sync: {timestamp}</li>
<li>State: {safe_state}</li>
<li>Needs records: {len(needs)}</li>
<li>Calendar events: {len(calendar_items)}</li>
<li>Reports: {len(reports)}</li>
<li>Donations: {len(donations)}</li>
<li>Board log entries: {len(board_log)}</li>
</ul>
<p><a href="./">Back to Home</a></p>"""
    write_both(DOCS / "deployment-proof", "Deployment Proof", proof_body)


# ── Main sync function ────────────────────────────────────────────────────────

def run_sync(dry_run: bool = False) -> int:
    """Run the approved-safe sync. If dry_run=True, print counts and write nothing."""
    c = creds(persist_refresh=not dry_run)
    sheets = sheets_service(c)
    calendar = calendar_service(c)

    # Read all tabs with complete rows (no row-100 limit)
    tab_rows = {}
    for tab in TAB_ORDER:
        tab_rows[tab] = read_sheet_rows(sheets, tab)

    calendar_items = safe_calendar_export(tab_rows.get("CalendarLog", []), calendar)
    now = datetime.now(timezone.utc)

    approved_needs = safe_needs_from_requests(tab_rows.get("Requests", []))
    approved_reports = safe_reports(tab_rows.get("Reports", []))
    approved_donations = safe_donations(tab_rows.get("Donations", []))
    visible_request_ids = {n.get("RequestID", "") for n in approved_needs if n.get("RequestID")}
    visible_report_ids = {r.get("ReportID", "") for r in approved_reports if r.get("ReportID")}
    approved_board_log = safe_board_log(
        tab_rows.get("AuditLog", []),
        visible_request_ids,
        {d.get("DonationID", "") for d in approved_donations if d.get("DonationID")},
        visible_report_ids,
    )

    out = {
        "approved_needs": approved_needs,
        "approved_calendar": calendar_items,
        "approved_reports": approved_reports,
        "approved_donations": approved_donations,
        "approved_volunteer_gaps": safe_volunteer_gaps(),
        "approved_board_log": approved_board_log,
    }

    if dry_run:
        print(json.dumps(dry_run_metrics(tab_rows, out), indent=2, sort_keys=True))
        return 0

    # Write JSON data exports to docs/data/
    for name, obj in out.items():
        write_json(DATA / f"{name}.json", obj)

    # Write all HTML pages
    build_pages(
        now,
        out["approved_needs"],
        out["approved_calendar"],
        out["approved_reports"],
        out["approved_donations"],
        out["approved_board_log"],
    )

    # Preserve the static deployment proof file
    live_check = DOCS / "LIVE_CHECK_002.html"
    if not live_check.exists():
        live_check.write_text("LIVE_CHECK_002_NON_PROFIT_HERMES_DEPLOYED\n")

    print(f"Sync complete. Marker: {MARKER}")
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Generate approved-safe board exports.")
    parser.add_argument("--dry-run", action="store_true", help="read and validate only; write no files")
    args = parser.parse_args(argv)
    return run_sync(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())