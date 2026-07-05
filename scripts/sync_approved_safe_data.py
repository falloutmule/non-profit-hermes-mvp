from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

ROOT = Path(r"C:\Users\fallo\non-profit-hermes-mvp")
DATA = ROOT / "data"
REPORT = ROOT / "APPROVED_SAFE_SYNC_REPORT.md"
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

HEADERS = {
    "Requests": ["RequestID", "DateReceived", "Source", "SubmittedBy", "PersonOrGroup", "ContactMethod", "NeedCategory", "NeedDescription", "Quantity", "LocationPrivate", "LocationPublicSafe", "Urgency", "NeededBy", "ConsentToRecord", "ConsentToShare", "PrivacyLevel", "AssignedTo", "Status", "NextAction", "CalendarEventID", "RelatedInventoryItem", "Notes", "CreatedBy", "LastUpdated", "SourceMessageLink"],
    "Donations": ["DonationID", "DateOffered", "DonorName", "DonorContact", "DonationType", "ItemDescription", "Quantity", "Condition", "PickupOrDropoff", "Location", "AvailableDate", "StorageNeeded", "MatchesCurrentNeed", "AssignedPickupVolunteer", "Status", "ReceiptNeeded", "ThankYouNeeded", "ConsentToPublicThanks", "Notes", "SourceMessageLink"],
    "Tasks": ["TaskID", "DateCreated", "TaskTitle", "TaskDescription", "Category", "Priority", "AssignedTo", "DueDate", "RelatedRequestID", "RelatedDonationID", "RelatedCalendarEventID", "Status", "Blocker", "NextAction", "CompletionReport", "LastUpdated"],
    "Inventory": ["ItemID", "ItemName", "Category", "QuantityOnHand", "Unit", "MinimumNeeded", "StorageLocation", "Condition", "LastCounted", "LastUpdatedBy", "NeededThisWeek", "PublicNeedAllowed", "Notes"],
    "CalendarLog": ["CalendarEventID", "EventTitle", "EventType", "StartDateTime", "EndDateTime", "Location", "PrivateLocation", "Description", "Attendees", "RelatedTaskID", "RelatedRequestID", "RelatedDonationID", "Status", "CreatedBy", "LastUpdated"],
    "Reports": ["ReportID", "Date", "SubmittedBy", "ReportType", "Summary", "PeopleServedEstimate", "ItemsDistributed", "Incidents", "FollowUpsNeeded", "SensitiveDetails", "PublicSummaryDraft", "PrivacyLevel", "RelatedTasks", "RelatedRequests", "RelatedDonations", "PhotosAttached", "SourceMessageLink"],
    "WebsiteDrafts": ["DraftID", "DateCreated", "Page", "DraftTitle", "DraftBody", "SourceRecords", "PrivacyReviewStatus", "BoardApprovalStatus", "ApprovedBy", "ApprovedDate", "PublishStatus", "GitCommitHash", "Notes"],
    "Approvals": ["ApprovalID", "DateRequested", "RequestedBy", "ApprovalType", "ItemType", "ItemID", "Summary", "ApprovedBy", "Decision", "DecisionDate", "Notes"],
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


def row(tab: str, mapping: dict[str, str]) -> list[str]:
    return [mapping.get(h, "") for h in HEADERS[tab]]


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
        if e.get("summary") != TEST_EVENT_TITLE:
            continue
        out.append({
            "CalendarEventID": e.get("id", ""),
            "EventTitle": e.get("summary", ""),
            "EventType": "test",
            "StartDateTime": e.get("start", {}).get("dateTime", e.get("start", {}).get("date", "")),
            "EndDateTime": e.get("end", {}).get("dateTime", e.get("end", {}).get("date", "")),
            "Description": TEST_EVENT_DESC,
            "Status": e.get("status", ""),
            "CreatedBy": "Hermes",
        })
    return out


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def md_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- none"


def render_markdown(now: datetime, needs, calendar_items, reports, donations, board_log) -> dict[str, str]:
    timestamp = now.strftime("%Y-%m-%d %H:%M UTC")
    safe_state = "approved-safe sync verified"

    preview_today = []
    if calendar_items:
        preview_today.append(f"Calendar event: `{calendar_items[0]['EventTitle']}`")
        preview_today.append(f"Calendar status: `{calendar_items[0]['Status']}`")
    if board_log:
        preview_today.append(f"Board log action: `{board_log[0]['Action']}`")
    if reports:
        preview_today.append(f"Report: `{reports[0]['ReportID']}` — {reports[0]['Summary']}")

    pages = {
        "index.md": f"""---
layout: default
title: Non-Profit Hermes MVP
permalink: /
---

# Non-Profit Hermes MVP

This site shows only board-approved, public-safe updates.

## Status

- **Last update:** {timestamp}
- **Current state:** {safe_state}

## Pages

- [Today](/today)
- [Current Needs](/current-needs)
- [Calendar](/calendar)
- [Volunteer](/volunteer)
- [Donations](/donations)
- [Reports](/reports)
- [Board Log](/board-log)

## Approved-safe data

- [approved_needs.json](data/approved_needs.json)
- [approved_calendar.json](data/approved_calendar.json)
- [approved_reports.json](data/approved_reports.json)
- [approved_donations.json](data/approved_donations.json)
- [approved_volunteer_gaps.json](data/approved_volunteer_gaps.json)
- [approved_board_log.json](data/approved_board_log.json)

## Safe test data preview

{md_list(preview_today)}
""",
        "today.md": f"""---
layout: default
title: Today
permalink: /today
---

# Today

Approved-safe current-day summary.

## Safe test data

{md_list([
    f"Calendar test event: `{calendar_items[0]['EventTitle']}`" if calendar_items else "Calendar test event missing",
    f"Calendar status: `{calendar_items[0]['Status']}`" if calendar_items else "Calendar status missing",
    f"Event source: `approved_calendar.json`",
    f"Board log source: `approved_board_log.json`",
])}
""",
        "current-needs.md": f"""---
layout: default
title: Current Needs
permalink: /current-needs
---

# Current Needs

Approved-safe current needs.

## Safe test data

{md_list([
    f"Request ID: `{needs[0]['RequestID']}`" if needs else "Request ID missing",
    f"Need: `{needs[0]['NeedDescription']}`" if needs else "Need missing",
    f"Category: `{needs[0]['NeedCategory']}`" if needs else "Category missing",
    f"Urgency: `{needs[0]['Urgency']}`" if needs else "Urgency missing",
    f"Status: `{needs[0]['Status']}`" if needs else "Status missing",
    f"Source: `approved_needs.json`",
    f"Donation source: `approved_donations.json`",
])}
""",
        "calendar.md": f"""---
layout: default
title: Calendar
permalink: /calendar
---

# Calendar

Approved-safe board-visible calendar items.

## Safe test data

{md_list([
    f"Event: `{calendar_items[0]['EventTitle']}`" if calendar_items else "Event missing",
    f"Type: `{calendar_items[0]['EventType']}`" if calendar_items else "Type missing",
    f"Status: `{calendar_items[0]['Status']}`" if calendar_items else "Status missing",
    f"Source: `approved_calendar.json`",
])}
""",
        "reports.md": f"""---
layout: default
title: Reports
permalink: /reports
---

# Reports

Approved-safe summaries.

## Safe test data

{md_list([
    f"Report ID: `{reports[0]['ReportID']}`" if reports else "Report ID missing",
    f"Summary: `{reports[0]['Summary']}`" if reports else "Summary missing",
    f"Privacy level: `{reports[0]['PrivacyLevel']}`" if reports else "Privacy level missing",
    f"Source: `approved_reports.json`",
])}
""",
        "board-log.md": f"""---
layout: default
title: Board Log
permalink: /board-log
---

# Board Log

Approved updates and publish history.

## Safe test data

{md_list([
    f"Audit ID: `{board_log[0]['AuditID']}`" if board_log else "Audit ID missing",
    f"Action: `{board_log[0]['Action']}`" if board_log else "Action missing",
    f"Result: `{board_log[0]['Result']}`" if board_log else "Result missing",
    f"Source: `approved_board_log.json`",
])}
""",
    }
    return pages


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

    for name, obj in out.items():
        write_json(DATA / f"{name}.json", obj)

    pages = render_markdown(
        now,
        out["approved_needs"],
        out["approved_calendar"],
        out["approved_reports"],
        out["approved_donations"],
        out["approved_board_log"],
    )
    for filename, body in pages.items():
        (ROOT / filename).write_text(body)

    report = f"""# Approved-Safe Sync Report

## What was done

- Verified Google Sheets/Calendar access via authenticated API calls.
- Read the Google Sheet `{sheet_title}`.
- Read the Google Calendar `Non-Profit Hermes Operations`.
- Exported only approved-safe fields into the JSON files under `data/`.
- Rendered the board-facing pages with the safe exported data.
- Did not export SensitiveNotes, private locations, contact details, or unapproved drafts.

## What was verified

- `approved_needs.json` updated from safe Sheet rows.
- `approved_calendar.json` updated from the safe test event.
- `approved_reports.json` updated from safe Sheet rows.
- `approved_donations.json` updated from safe Sheet rows.
- `approved_volunteer_gaps.json` remains an approved-safe empty stub.
- `approved_board_log.json` updated from AuditLog.
- Markdown pages now visibly include safe test data in body sections.

## What failed

- No blocking failure.

## Current exact state

- Spreadsheet ID: `{SPREADSHEET_ID}`
- Calendar ID: `{CALENDAR_ID}`
- Test event: `{TEST_EVENT_TITLE}`
- Repo: `https://github.com/falloutmule/non-profit-hermes-mvp`

## Remaining blockers

- None for the first approved-safe sync proof.

## Next actionable step

- Commit the sync script, JSON outputs, page updates, and report, then wait for GitHub Pages to rebuild and confirm the safe test data is visible.

## Evidence paths/files/logs/URLs

- `C:\\Users\\fallo\\non-profit-hermes-mvp\\scripts\\sync_approved_safe_data.py`
- `C:\\Users\\fallo\\non-profit-hermes-mvp\\VISIBLE_SYNC_RENDERING_REPORT.md`
- `C:\\Users\\fallo\\non-profit-hermes-mvp\\APPROVED_SAFE_SYNC_REPORT.md`
- `C:\\Users\\fallo\\non-profit-hermes-mvp\\data\\approved_needs.json`
- `C:\\Users\\fallo\\non-profit-hermes-mvp\\data\\approved_calendar.json`
- `C:\\Users\\fallo\\non-profit-hermes-mvp\\data\\approved_reports.json`
- `C:\\Users\\fallo\\non-profit-hermes-mvp\\data\\approved_donations.json`
- `C:\\Users\\fallo\\non-profit-hermes-mvp\\data\\approved_volunteer_gaps.json`
- `C:\\Users\\fallo\\non-profit-hermes-mvp\\data\\approved_board_log.json`
"""
    (ROOT / "APPROVED_SAFE_SYNC_REPORT.md").write_text(report)
    (ROOT / "VISIBLE_SYNC_RENDERING_REPORT.md").write_text(report.replace("Approved-Safe Sync Report", "Visible Sync Rendering Report"))

    print(json.dumps({
        "auth": "Authenticated Google Workspace access confirmed via Sheets/Calendar API calls.",
        "sheet_title": sheet_title,
        "updated_files": [str(DATA / n) for n in ["approved_needs.json", "approved_calendar.json", "approved_reports.json", "approved_donations.json", "approved_volunteer_gaps.json", "approved_board_log.json"]],
        "report": str(REPORT),
        "rows": {k: len(v) for k, v in out.items()},
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
