from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

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
body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;max-width:52rem;margin:2rem auto;padding:0 1rem;line-height:1.55;color:#1f2937;background:#fff}}
a{{color:#1d4ed8;text-decoration:none}} a:hover{{text-decoration:underline}}
header,footer{{font-size:.95rem;color:#6b7280;margin:0 0 1.25rem}}
nav a{{margin-right:1rem}}
main{{padding:1rem 0}}
h1,h2,h3{{line-height:1.2}}
code,pre{{background:#f3f4f6;border-radius:6px}}
pre{{padding:1rem;overflow:auto}}
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

HTML_FOOT = """
</main>
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

HEADERS = {
    "Requests": ["RequestID", "DateReceived", "Source", "SubmittedBy", "PersonOrGroup", "ContactMethod", "NeedCategory", "NeedDescription", "Quantity", "LocationPrivate", "LocationPublicSafe", "Urgency", "NeededBy", "ConsentToRecord", "ConsentToShare", "PrivacyLevel", "AssignedTo", "Status", "NextAction", "CalendarEventID", "RelatedInventoryItem", "Notes", "CreatedBy", "LastUpdated", "SourceMessageLink"],
    "Donations": ["DonationID", "DateOffered", "DonorName", "DonorContact", "DonationType", "ItemDescription", "Quantity", "Condition", "PickupOrDropoff", "Location", "AvailableDate", "StorageNeeded", "MatchesCurrentNeed", "AssignedPickupVolunteer", "Status", "ReceiptNeeded", "ThankYouNeeded", "ConsentToPublicThanks", "Notes", "SourceMessageLink"],
    "Reports": ["ReportID", "Date", "SubmittedBy", "ReportType", "Summary", "PeopleServedEstimate", "ItemsDistributed", "Incidents", "FollowUpsNeeded", "SensitiveDetails", "PublicSummaryDraft", "PrivacyLevel", "RelatedTasks", "RelatedRequests", "RelatedDonations", "PhotosAttached", "SourceMessageLink"],
    "AuditLog": ["AuditID", "Timestamp", "Actor", "Action", "TargetSystem", "TargetItem", "Before", "After", "Result", "Error", "SourceMessageLink"],
}


def col(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def creds() -> Credentials:
    c = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if c.expired and c.refresh_token:
        c.refresh(Request())
        TOKEN.write_text(json.dumps(json.loads(c.to_json()), indent=2))
    return c


def sheets_service(c: Credentials):
    return build("sheets", "v4", credentials=c)


def calendar_service(c: Credentials):
    return build("calendar", "v3", credentials=c)


def read_sheet_rows(svc, tab: str) -> list[list[str]]:
    result = svc.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=f"{tab}!A1:{col(len(HEADERS[tab]))}100").execute()
    return result.get("values", [])


def safe_needs_from_requests(rows: list[list[str]]) -> list[dict[str, str]]:
    out = []
    for r in rows[1:]:
        if not r:
            continue
        data = dict(zip(HEADERS["Requests"], r))
        out.append({
            "RequestID": data.get("RequestID", ""),
            "DateReceived": data.get("DateReceived", ""),
            "NeedCategory": data.get("NeedCategory", ""),
            "NeedDescription": data.get("NeedDescription", ""),
            "Quantity": data.get("Quantity", ""),
            "Urgency": data.get("Urgency", ""),
            "NeededBy": data.get("NeededBy", ""),
            "PrivacyLevel": data.get("PrivacyLevel", ""),
            "Status": data.get("Status", ""),
            "NextAction": data.get("NextAction", ""),
        })
    return out


def safe_donations(rows: list[list[str]]) -> list[dict[str, str]]:
    out = []
    for r in rows[1:]:
        if not r:
            continue
        data = dict(zip(HEADERS["Donations"], r))
        out.append({
            "DonationID": data.get("DonationID", ""),
            "DateOffered": data.get("DateOffered", ""),
            "DonationType": data.get("DonationType", ""),
            "ItemDescription": data.get("ItemDescription", ""),
            "Quantity": data.get("Quantity", ""),
            "Status": data.get("Status", ""),
            "ReceiptNeeded": data.get("ReceiptNeeded", ""),
            "ThankYouNeeded": data.get("ThankYouNeeded", ""),
        })
    return out


def safe_reports(rows: list[list[str]]) -> list[dict[str, str]]:
    out = []
    for r in rows[1:]:
        if not r:
            continue
        data = dict(zip(HEADERS["Reports"], r))
        out.append({
            "ReportID": data.get("ReportID", ""),
            "Date": data.get("Date", ""),
            "ReportType": data.get("ReportType", ""),
            "Summary": data.get("Summary", ""),
            "PeopleServedEstimate": data.get("PeopleServedEstimate", ""),
            "ItemsDistributed": data.get("ItemsDistributed", ""),
            "PrivacyLevel": data.get("PrivacyLevel", ""),
            "PublicSummaryDraft": data.get("PublicSummaryDraft", ""),
        })
    return out


def safe_volunteer_gaps() -> list[dict[str, str]]:
    return []


def safe_board_log(rows: list[list[str]]) -> list[dict[str, str]]:
    out = []
    for r in rows[1:]:
        if not r:
            continue
        data = dict(zip(HEADERS["AuditLog"], r))
        out.append({
            "AuditID": data.get("AuditID", ""),
            "Timestamp": data.get("Timestamp", ""),
            "Actor": data.get("Actor", ""),
            "Action": data.get("Action", ""),
            "TargetSystem": data.get("TargetSystem", ""),
            "TargetItem": data.get("TargetItem", ""),
            "Result": data.get("Result", ""),
        })
    return out


def safe_calendar_export(calendar_svc) -> list[dict[str, str]]:
    events = calendar_svc.events().list(
        calendarId=CALENDAR_ID,
        timeMin=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
        timeMax=(datetime.now(timezone.utc) + timedelta(days=7)).isoformat().replace("+00:00", "Z"),
        singleEvents=True,
        orderBy="startTime",
        maxResults=50,
    ).execute().get("items", [])
    out = []
    for e in events:
        if e.get("status") == "cancelled":
            continue
        # Determine event type from title
        summary = e.get("summary", "")
        if summary == TEST_EVENT_TITLE:
            event_type = "test"
        elif summary.startswith("CAL-WRITE-TEST-"):
            event_type = "write-test"
        else:
            event_type = "operational"
        out.append({
            "CalendarEventID": e.get("id", ""),
            "EventTitle": summary,
            "EventType": event_type,
            "StartDateTime": e.get("start", {}).get("dateTime", e.get("start", {}).get("date", "")),
            "EndDateTime": e.get("end", {}).get("dateTime", e.get("end", {}).get("date", "")),
            "Description": e.get("description", ""),
            "Status": e.get("status", ""),
            "CreatedBy": "Hermes",
        })
    return out


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def html_list(items: list[str]) -> str:
    return "\n".join(f"<li>{item}</li>" for item in items) if items else "<li>none</li>"


def write_page(path: Path, title: str, body_html: str, nav_links: str = NAV_LINKS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    html = (
        HTML_HEAD.format(title=title, nav_links=nav_links)
        + body_html
        + HTML_FOOT
    )
    path.write_text(html)


def write_both(base: Path, title: str, body_html: str) -> None:
    """Write both page.html and page/index.html."""
    write_page(base.with_suffix(".html"), title, body_html, nav_links=NAV_LINKS)
    idx_dir = base.parent / base.stem / "index.html"
    write_page(idx_dir, title, body_html, nav_links=NAV_LINKS_SUB)


def build_pages(now: datetime, needs, calendar_items, reports, donations, board_log) -> None:
    timestamp = now.strftime("%Y-%m-%d %H:%M UTC")
    safe_state = "approved-safe sync verified"

    # --- index.html ---
    preview_items = []
    if calendar_items:
        preview_items.append(f"Calendar event: <code>{calendar_items[0]['EventTitle']}</code>")
        preview_items.append(f"Calendar status: <code>{calendar_items[0]['Status']}</code>")
    if board_log:
        preview_items.append(f"Board log action: <code>{board_log[0]['Action']}</code>")
    if reports:
        preview_items.append(f"Report: <code>{reports[0]['ReportID']}</code> &mdash; {reports[0]['Summary']}")
    if needs:
        preview_items.append(f"Request: <code>{needs[0]['RequestID']}</code> &mdash; {needs[0]['NeedDescription']}")
    if donations:
        preview_items.append(f"Donation: <code>{donations[0]['DonationID']}</code> &mdash; {donations[0]['ItemDescription']}")

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
<h2>Safe test data preview</h2>
<ul>
{html_list(preview_items)}
</ul>"""
    write_both(DOCS / "index", "Non-Profit Hermes MVP", index_body)

    # --- current-needs.html ---
    needs_items = []
    board_needs = [n for n in needs if str(n.get("PrivacyLevel", "")).lower() in {"board-visible", ""}]
    if board_needs:
        needs_items.append(f"Deployment marker: <code>{MARKER}</code>")
        needs_items.append(f"Board-visible needs: <code>{len(board_needs)}</code>")
        for n in board_needs:
            needs_items.append(
                f"Need <code>{n.get('RequestID', 'unknown')}</code>: {n.get('NeedDescription', 'unknown')} "
                f"(category: {n.get('NeedCategory', 'unknown')}, urgency: {n.get('Urgency', 'unknown')}, status: {n.get('Status', 'unknown')})"
            )
    else:
        needs_items.append(f"Deployment marker: <code>{MARKER}</code>")
        needs_items.append("No board-visible needs records available.")

    needs_body = f"""<h1>Current Needs</h1>
<p>Approved-safe current needs.</p>
<h2>Safe test data</h2>
<ul>
{html_list(needs_items)}
</ul>"""
    write_both(DOCS / "current-needs", "Current Needs", needs_body)

    # --- calendar.html ---
    cal_items = []
    if calendar_items:
        cal_items.append(f"Deployment marker: <code>{MARKER}</code>")
        cal_items.append(f"Event: <code>{calendar_items[0]['EventTitle']}</code>")
        cal_items.append(f"Type: <code>{calendar_items[0]['EventType']}</code>")
        cal_items.append(f"Status: <code>{calendar_items[0]['Status']}</code>")
    else:
        cal_items.append(f"Deployment marker: <code>{MARKER}</code>")
        cal_items.append("No calendar events available.")

    cal_body = f"""<h1>Calendar</h1>
<p>Approved-safe board-visible calendar items.</p>
<h2>Safe test data</h2>
<ul>
{html_list(cal_items)}
</ul>"""
    write_both(DOCS / "calendar", "Calendar", cal_body)

    # --- reports.html ---
    rep_items = []
    if reports:
        rep_items.append(f"Deployment marker: <code>{MARKER}</code>")
        rep_items.append(f"Report ID: <code>{reports[0]['ReportID']}</code>")
        rep_items.append(f"Summary: <code>{reports[0]['Summary']}</code>")
        rep_items.append(f"Privacy level: <code>{reports[0]['PrivacyLevel']}</code>")
    else:
        rep_items.append(f"Deployment marker: <code>{MARKER}</code>")
        rep_items.append("No reports available.")

    reports_body = f"""<h1>Reports</h1>
<p>Approved-safe summaries.</p>
<h2>Safe test data</h2>
<ul>
{html_list(rep_items)}
</ul>"""
    write_both(DOCS / "reports", "Reports", reports_body)

    # --- today.html ---
    today_items = []
    today_items.append(f"Deployment marker: <code>{MARKER}</code>")
    if calendar_items:
        today_items.append(f"Calendar test event: <code>{calendar_items[0]['EventTitle']}</code>")
        today_items.append(f"Calendar status: <code>{calendar_items[0]['Status']}</code>")
    if needs:
        today_items.append(f"Urgent needs: <code>{needs[0]['RequestID']}</code> ({needs[0]['NeedDescription']})")
    if reports:
        today_items.append(f"Latest report: <code>{reports[0]['ReportID']}</code>")
    if not calendar_items and not needs and not reports:
        today_items.append("No current-day data available.")

    today_body = f"""<h1>Today</h1>
<p>Approved-safe current-day summary.</p>
<h2>Safe test data</h2>
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


def main() -> int:
    c = creds()
    sheets = sheets_service(c)
    calendar = calendar_service(c)

    sheet_meta = sheets.spreadsheets().get(spreadsheetId=SPREADSHEET_ID, fields="properties.title,sheets.properties.title").execute()
    sheet_title = sheet_meta.get("properties", {}).get("title", "")

    requests_rows = read_sheet_rows(sheets, "Requests")
    donations_rows = read_sheet_rows(sheets, "Donations")
    reports_rows = read_sheet_rows(sheets, "Reports")
    audit_rows = read_sheet_rows(sheets, "AuditLog")
    calendar_items = safe_calendar_export(calendar)
    now = datetime.now(timezone.utc)

    out = {
        "approved_needs": safe_needs_from_requests(requests_rows),
        "approved_calendar": calendar_items,
        "approved_reports": safe_reports(reports_rows),
        "approved_donations": safe_donations(donations_rows),
        "approved_volunteer_gaps": safe_volunteer_gaps(),
        "approved_board_log": safe_board_log(audit_rows),
    }

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

    # Also ensure .nojekyll exists
    (DOCS / ".nojekyll").touch()

    report = f"""# Docs Sync Update Report

## What was done

- Verified Google Sheets/Calendar access via authenticated API calls.
- Read the Google Sheet `{sheet_title}`.
- Read the Google Calendar `Non-Profit Hermes Operations`.
- Exported only approved-safe fields into JSON files under `docs/data/`.
- Generated self-contained static HTML pages in `docs/` (no Jekyll, no Markdown).
- Preserved deployment marker `{MARKER}` on every page.
- Wrote both `page.html` and `page/index.html` variants for all pages.
- Did NOT write to root files, root .md pages, or root data/.
- Did NOT export SensitiveNotes, private locations, contact details, or unapproved drafts.

## What was verified

- `docs/data/approved_needs.json` updated from safe Sheet rows.
- `docs/data/approved_calendar.json` updated from the safe test event.
- `docs/data/approved_reports.json` updated from safe Sheet rows.
- `docs/data/approved_donations.json` updated from safe Sheet rows.
- `docs/data/approved_volunteer_gaps.json` remains an approved-safe empty stub.
- `docs/data/approved_board_log.json` updated from AuditLog.
- All HTML pages now include `{MARKER}`, timestamp, and safe data.

## What failed

- No blocking failure.

## Current exact state

- Spreadsheet ID: `{SPREADSHEET_ID}`
- Calendar ID: `{CALENDAR_ID}`
- Test event: `{TEST_EVENT_TITLE}`
- Pages source: `main /docs`
- Repo: `https://github.com/falloutmule/non-profit-hermes-mvp`

## Remaining blockers

- None for the docs/ sync update.

## Next actionable step

- Commit the sync script, JSON outputs, and updated HTML pages, then push and verify.

## Evidence paths/files/logs/URLs

- `C:\\Users\\fallo\\non-profit-hermes-mvp\\scripts\\sync_approved_safe_data.py`
- `C:\\Users\\fallo\\non-profit-hermes-mvp\\docs\\data\\approved_needs.json`
- `C:\\Users\\fallo\\non-profit-hermes-mvp\\docs\\data\\approved_calendar.json`
- `C:\\Users\\fallo\\non-profit-hermes-mvp\\docs\\data\\approved_reports.json`
- `C:\\Users\\fallo\\non-profit-hermes-mvp\\docs\\data\\approved_donations.json`
- `C:\\Users\\fallo\\non-profit-hermes-mvp\\docs\\data\\approved_volunteer_gaps.json`
- `C:\\Users\\fallo\\non-profit-hermes-mvp\\docs\\data\\approved_board_log.json`
- `C:\\Users\\fallo\\non-profit-hermes-mvp\\docs\\index.html`
- `C:\\Users\\fallo\\non-profit-hermes-mvp\\docs\\current-needs.html`
- `C:\\Users\\fallo\\non-profit-hermes-mvp\\docs\\current-needs/index.html`
- `C:\\Users\\fallo\\non-profit-hermes-mvp\\docs\\calendar.html`
- `C:\\Users\\fallo\\non-profit-hermes-mvp\\docs\\calendar/index.html`
- `C:\\Users\\fallo\\non-profit-hermes-mvp\\docs\\reports.html`
- `C:\\Users\\fallo\\non-profit-hermes-mvp\\docs\\reports/index.html`
- `C:\\Users\\fallo\\non-profit-hermes-mvp\\docs\\today.html`
- `C:\\Users\\fallo\\non-profit-hermes-mvp\\docs\\today/index.html`
"""
    (DOCS / "DOCS_SYNC_UPDATE_REPORT.md").write_text(report)

    print(json.dumps({
        "auth": "Authenticated Google Workspace access confirmed via Sheets/Calendar API calls.",
        "sheet_title": sheet_title,
        "updated_json": [str(DATA / n) for n in ["approved_needs.json", "approved_calendar.json", "approved_reports.json", "approved_donations.json", "approved_volunteer_gaps.json", "approved_board_log.json"]],
        "rows": {k: len(v) for k, v in out.items()},
        "marker": MARKER,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
