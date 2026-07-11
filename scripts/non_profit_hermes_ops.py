"""
non_profit_hermes_ops.py — Backend write operations for Non-Profit Hermes.

Each operation writes to the correct Google Sheet tab and creates an AuditLog row.
Calendar operations create real events in the Non-Profit Hermes Operations calendar.

CLI usage:
    python scripts/non_profit_hermes_ops.py --test-write
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

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
)

# ── Shared config ────────────────────────────────────────────────────────────

ROOT = Path(r"C:\Users\fallo\non-profit-hermes-mvp")
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

AUDIT_HEADERS = HEADERS["AuditLog"]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def ts() -> str:
    return now_utc().isoformat(timespec="seconds")


def gen_id(prefix: str = "NPH") -> str:
    """Generate a unique ID like NPH-A1B2C3D4."""
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def _row_exists(svc, tab: str, id_col: str, id_value: str) -> bool:
    """Check if a row with the given ID already exists in the tab."""
    try:
        rows = svc.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{tab}!A1:Z500"
        ).execute().get("values", [])
        if not rows:
            return False
        header = [h.strip() for h in rows[0]]
        if id_col not in header:
            return False
        col_idx = header.index(id_col)
        return any(len(r) > col_idx and r[col_idx].strip() == str(id_value) for r in rows[1:])
    except Exception:
        return False


def _calendar_event_exists(svc_cal, title: str) -> str | None:
    """Search calendar for an event with the given title. Returns event ID if found."""
    try:
        events = svc_cal.events().list(
            calendarId=CALENDAR_ID,
            q=title,
            singleEvents=True,
            maxResults=10,
        ).execute().get("items", [])
        for e in events:
            if e.get("summary") == title:
                return e.get("id")
        return None
    except Exception:
        return None


# ── Auth / Services ─────────────────────────────────────────────────────────

def get_creds() -> Credentials:
    c = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if c.expired and c.refresh_token:
        c.refresh(Request())
        TOKEN.write_text(json.dumps(json.loads(c.to_json()), indent=2))
    return c


def sheets(creds: Credentials):
    return build("sheets", "v4", credentials=creds)


def calendar(creds: Credentials):
    return build("calendar", "v3", credentials=creds)


# ── Sheet write helpers ────────────────────────────────────────────────────

def append_row(svc, tab: str, values: list[Any]) -> dict:
    """Append a row to the given tab."""
    range_end = col(len(HEADERS[tab]))
    body = {"values": [values]}
    result = svc.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{tab}!A1:{range_end}",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body=body,
    ).execute()
    return result


def make_row(tab: str, mapping: dict[str, str]) -> list[str]:
    """Build a row list from a partial mapping; missing cols become ''."""
    return [mapping.get(h, "") for h in HEADERS[tab]]


def ensure_header(svc, tab: str) -> None:
    """Ensure the header row for the given tab matches HEADERS[tab]."""
    range_end = col(len(HEADERS[tab]))
    body = {"values": [HEADERS[tab]]}
    svc.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{tab}!A1:{range_end}1",
        valueInputOption="USER_ENTERED",
        body=body,
    ).execute()


# ── AuditLog helper ─────────────────────────────────────────────────────────

def write_audit_log(
    svc,
    actor: str,
    action: str,
    target_system: str,
    target_item: str,
    before: str = "",
    after: str = "",
    result: str = "success",
    error: str = "",
    source_link: str = "",
) -> str:
    """Write a row to the AuditLog tab. Returns the AuditID."""
    audit_id = f"AUDIT-{uuid.uuid4().hex[:8].upper()}"
    row = make_row("AuditLog", {
        "AuditID": audit_id,
        "Timestamp": ts(),
        "Actor": actor,
        "Action": action,
        "TargetSystem": target_system,
        "TargetItem": target_item,
        "Before": before,
        "After": after,
        "Result": result,
        "Error": error,
        "SourceMessageLink": source_link,
    })
    append_row(svc, "AuditLog", row)
    return audit_id


# ── Primary operations ──────────────────────────────────────────────────────

def _find_row_by_id(svc, tab: str, id_col: str, id_value: str) -> tuple[int, list[str], list[str]] | None:
    """Return (row_number, header, row_values) for the matching ID, or None."""
    rows = svc.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{tab}!A1:Z1000",
    ).execute().get("values", [])
    if not rows:
        return None
    header = [h.strip() for h in rows[0]]
    if id_col not in header:
        return None
    col_idx = header.index(id_col)
    for idx, row in enumerate(rows[1:], start=2):
        if len(row) > col_idx and row[col_idx].strip() == str(id_value):
            return idx, header, row
    return None


def add_request(
    svc,
    *,
    request_id: str = "",
    source: str = "Hermes",
    submitted_by: str = "Hermes",
    person_or_group: str = "",
    contact_method: str = "",
    need_category: str = "other",
    need_description: str = "",
    quantity: str = "",
    location_private: str = "",
    location_public_safe: str = "",
    urgency: str = "low",
    needed_by: str = "",
    privacy_level: str = "board-visible",
    status: str = "new",
    next_action: str = "",
    notes: str = "",
    created_by: str = "Hermes",
    source_link: str = "",
) -> dict:
    """Add a request row to the Requests tab. Idempotent on RequestID."""
    rid = request_id or gen_id("REQ")
    if _row_exists(svc, "Requests", "RequestID", rid):
        write_audit_log(svc, "Hermes", "duplicate_skipped", "Google Sheets", f"Requests/{rid}",
                         after=f"Request {rid} already exists; duplicate skipped")
        return {"tab": "Requests", "id": rid, "status": "already_exists"}
    now_ts = ts()
    row = make_row("Requests", {
        "RequestID": rid,
        "DateReceived": now_ts,
        "Source": source,
        "SubmittedBy": submitted_by,
        "PersonOrGroup": person_or_group,
        "ContactMethod": contact_method,
        "NeedCategory": need_category,
        "NeedDescription": need_description,
        "Quantity": quantity,
        "LocationPrivate": location_private,
        "LocationPublicSafe": location_public_safe,
        "Urgency": urgency,
        "NeededBy": needed_by,
        "PrivacyLevel": privacy_level,
        "Status": status,
        "NextAction": next_action,
        "Notes": notes,
        "CreatedBy": created_by,
        "LastUpdated": now_ts,
        "SourceMessageLink": source_link,
    })
    result = append_row(svc, "Requests", row)
    write_audit_log(svc, "Hermes", "create", "Google Sheets", f"Requests/{rid}",
                     after=f"Request {rid} created: {need_description}")
    return {"tab": "Requests", "id": rid, "status": "created", "api_result": result}


def update_request(
    svc,
    *,
    request_id: str,
    source: str | None = None,
    submitted_by: str | None = None,
    person_or_group: str | None = None,
    contact_method: str | None = None,
    need_category: str | None = None,
    need_description: str | None = None,
    quantity: str | None = None,
    location_private: str | None = None,
    location_public_safe: str | None = None,
    urgency: str | None = None,
    needed_by: str | None = None,
    privacy_level: str | None = None,
    status: str | None = None,
    next_action: str | None = None,
    notes: str | None = None,
    created_by: str | None = None,
    source_link: str | None = None,
) -> dict:
    """Update an existing request row by RequestID."""
    found = _find_row_by_id(svc, "Requests", "RequestID", request_id)
    if not found:
        write_audit_log(svc, "Hermes", "update_missing", "Google Sheets", f"Requests/{request_id}",
                         after="Request not found", result="not_found")
        return {"tab": "Requests", "id": request_id, "status": "not_found"}

    row_num, header, row = found
    current = {header[i]: row[i] if i < len(row) else "" for i in range(len(header))}
    before = json.dumps({k: current.get(k, "") for k in [
        "NeedDescription", "Urgency", "NeededBy", "LocationPrivate", "LocationPublicSafe",
        "PrivacyLevel", "Status", "NextAction", "Notes", "LastUpdated", "SourceMessageLink",
    ]}, ensure_ascii=False)

    updates = {
        "Source": source,
        "SubmittedBy": submitted_by,
        "PersonOrGroup": person_or_group,
        "ContactMethod": contact_method,
        "NeedCategory": need_category,
        "NeedDescription": need_description,
        "Quantity": quantity,
        "LocationPrivate": location_private,
        "LocationPublicSafe": location_public_safe,
        "Urgency": urgency,
        "NeededBy": needed_by,
        "PrivacyLevel": privacy_level,
        "Status": status,
        "NextAction": next_action,
        "Notes": notes,
        "CreatedBy": created_by,
        "SourceMessageLink": source_link,
    }
    for key, value in updates.items():
        if value is not None:
            current[key] = value
    current["LastUpdated"] = ts()
    after = json.dumps({k: current.get(k, "") for k in [
        "NeedDescription", "Urgency", "NeededBy", "LocationPrivate", "LocationPublicSafe",
        "PrivacyLevel", "Status", "NextAction", "Notes", "LastUpdated", "SourceMessageLink",
    ]}, ensure_ascii=False)

    values = [current.get(h, "") for h in header]
    range_end = col(len(header))
    svc.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"Requests!A{row_num}:{range_end}{row_num}",
        valueInputOption="USER_ENTERED",
        body={"values": [values]},
    ).execute()

    write_audit_log(svc, "Hermes", "update", "Google Sheets", f"Requests/{request_id}",
                     before=before, after=after)
    return {"tab": "Requests", "id": request_id, "status": "updated"}


def add_donation(
    svc,
    *,
    donation_id: str = "",
    donor_name: str = "",
    donor_contact: str = "",
    donation_type: str = "other",
    item_description: str = "",
    quantity: str = "",
    condition: str = "new",
    pickup_or_dropoff: str = "",
    location: str = "",
    available_date: str = "",
    status: str = "new",
    receipt_needed: str = "",
    thank_you_needed: str = "",
    consent_to_public_thanks: str = "",
    next_action: str = "",
    notes: str = "",
    source_link: str = "",
    privacy_level: str = "private-review",
    public_listing_allowed: str = "",
) -> dict:
    """Add a donation row to the Donations tab. Idempotent on DonationID."""
    ensure_header(svc, "Donations")
    did = donation_id or gen_id("DON")
    if _row_exists(svc, "Donations", "DonationID", did):
        write_audit_log(svc, "Hermes", "duplicate_skipped", "Google Sheets", f"Donations/{did}",
                         after=f"Donation {did} already exists; duplicate skipped")
        return {"tab": "Donations", "id": did, "status": "already_exists"}
    now_ts = ts()
    row = make_row("Donations", {
        "DonationID": did,
        "DateOffered": now_ts,
        "DonorName": donor_name,
        "DonorContact": donor_contact,
        "DonationType": donation_type,
        "ItemDescription": item_description,
        "Quantity": quantity,
        "Condition": condition,
        "PickupOrDropoff": pickup_or_dropoff,
        "Location": location,
        "AvailableDate": available_date,
        "StorageNeeded": "",
        "MatchesCurrentNeed": "",
        "AssignedPickupVolunteer": "",
        "Status": status,
        "ReceiptNeeded": receipt_needed,
        "ThankYouNeeded": thank_you_needed,
        "ConsentToPublicThanks": consent_to_public_thanks,
        "PrivacyLevel": privacy_level,
        "PublicListingAllowed": public_listing_allowed,
        "NextAction": next_action,
        "Notes": notes,
        "SourceMessageLink": source_link,
        "LastUpdated": now_ts,
    })
    result = append_row(svc, "Donations", row)
    write_audit_log(svc, "Hermes", "create", "Google Sheets", f"Donations/{did}",
                     after=f"Donation {did} created: {item_description}")
    return {"tab": "Donations", "id": did, "status": "created", "api_result": result}


def update_donation(
    svc,
    *,
    donation_id: str,
    donor_name: str | None = None,
    donor_contact: str | None = None,
    donation_type: str | None = None,
    item_description: str | None = None,
    quantity: str | None = None,
    condition: str | None = None,
    pickup_or_dropoff: str | None = None,
    location: str | None = None,
    available_date: str | None = None,
    status: str | None = None,
    receipt_needed: str | None = None,
    thank_you_needed: str | None = None,
    consent_to_public_thanks: str | None = None,
    next_action: str | None = None,
    notes: str | None = None,
    source_link: str | None = None,
    privacy_level: str | None = None,
    public_listing_allowed: str | None = None,
) -> dict:
    """Update an existing donation row by DonationID."""
    ensure_header(svc, "Donations")
    found = _find_row_by_id(svc, "Donations", "DonationID", donation_id)
    if not found:
        write_audit_log(svc, "Hermes", "update_missing", "Google Sheets", f"Donations/{donation_id}",
                         after="Donation not found", result="not_found")
        return {"tab": "Donations", "id": donation_id, "status": "not_found"}

    row_num, header, row = found
    current = {header[i]: row[i] if i < len(row) else "" for i in range(len(header))}
    before = json.dumps({k: current.get(k, "") for k in [
        "DonationType", "ItemDescription", "Quantity", "Condition", "PickupOrDropoff",
        "Location", "AvailableDate", "Status", "ReceiptNeeded", "ThankYouNeeded",
        "ConsentToPublicThanks", "NextAction", "Notes", "LastUpdated", "SourceMessageLink",
    ]}, ensure_ascii=False)

    updates = {
        "DonorName": donor_name,
        "DonorContact": donor_contact,
        "DonationType": donation_type,
        "ItemDescription": item_description,
        "Quantity": quantity,
        "Condition": condition,
        "PickupOrDropoff": pickup_or_dropoff,
        "Location": location,
        "AvailableDate": available_date,
        "Status": status,
        "ReceiptNeeded": receipt_needed,
        "ThankYouNeeded": thank_you_needed,
        "ConsentToPublicThanks": consent_to_public_thanks,
        "PrivacyLevel": privacy_level,
        "PublicListingAllowed": public_listing_allowed,
        "NextAction": next_action,
        "Notes": notes,
        "SourceMessageLink": source_link,
    }
    for key, value in updates.items():
        if value is not None:
            current[key] = value
    current["LastUpdated"] = ts()
    after = json.dumps({k: current.get(k, "") for k in [
        "DonationType", "ItemDescription", "Quantity", "Condition", "PickupOrDropoff",
        "Location", "AvailableDate", "Status", "ReceiptNeeded", "ThankYouNeeded",
        "ConsentToPublicThanks", "NextAction", "Notes", "LastUpdated", "SourceMessageLink",
    ]}, ensure_ascii=False)

    values = [current.get(h, "") for h in header]
    range_end = col(len(header))
    svc.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"Donations!A{row_num}:{range_end}{row_num}",
        valueInputOption="USER_ENTERED",
        body={"values": [values]},
    ).execute()

    write_audit_log(svc, "Hermes", "update", "Google Sheets", f"Donations/{donation_id}",
                     before=before, after=after)
    return {"tab": "Donations", "id": donation_id, "status": "updated"}


def add_report(
    svc,
    *,
    report_id: str = "",
    submitted_by: str = "Hermes",
    report_type: str = "other",
    summary: str = "",
    privacy_level: str = "board-visible",
    sensitive_details: str = "",
    source_link: str = "",
    people_served_estimate: str = "",
    items_distributed: str = "",
    followups_needed: str = "",
    public_summary_draft: str = "",
    public_summary_allowed: str = "",
    status: str = "needs-info",
    next_action: str = "review",
) -> dict:
    """Add a report row to the Reports tab. Idempotent on ReportID."""
    ensure_header(svc, "Reports")
    rid = report_id or gen_id("REP")
    if _row_exists(svc, "Reports", "ReportID", rid):
        write_audit_log(svc, "Hermes", "duplicate_skipped", "Google Sheets", f"Reports/{rid}",
                         after=f"Report {rid} already exists; duplicate skipped")
        return {"tab": "Reports", "id": rid, "status": "already_exists"}
    ensure_header(svc, "Reports")
    now_ts = ts()
    row = make_row("Reports", {
        "ReportID": rid,
        "Date": now_ts,
        "SubmittedBy": submitted_by,
        "ReportType": report_type,
        "Summary": summary,
        "PeopleServedEstimate": people_served_estimate,
        "ItemsDistributed": items_distributed,
        "FollowUpsNeeded": followups_needed,
        "SensitiveDetails": sensitive_details,
        "PublicSummaryDraft": public_summary_draft,
        "PrivacyLevel": privacy_level,
        "Status": status,
        "NextAction": next_action,
        "Notes": "",
        "LastUpdated": now_ts,
        "SourceMessageLink": source_link,
        "PublicSummaryAllowed": public_summary_allowed,
    })
    result = append_row(svc, "Reports", row)
    write_audit_log(svc, "Hermes", "create", "Google Sheets", f"Reports/{rid}",
                     after=f"Report {rid} created: {summary}")
    return {"tab": "Reports", "id": rid, "status": "created", "api_result": result}


def update_report(
    svc,
    *,
    report_id: str,
    submitted_by: str | None = None,
    report_type: str | None = None,
    summary: str | None = None,
    people_served_estimate: str | None = None,
    items_distributed: str | None = None,
    followups_needed: str | None = None,
    sensitive_details: str | None = None,
    public_summary_draft: str | None = None,
    privacy_level: str | None = None,
    date: str | None = None,
    next_action: str | None = None,
    status: str | None = None,
    source_link: str | None = None,
    public_summary_allowed: str | None = None,
    notes: str | None = None,
) -> dict:
    """Update an existing report row by ReportID."""
    ensure_header(svc, "Reports")
    found = _find_row_by_id(svc, "Reports", "ReportID", report_id)
    if not found:
        write_audit_log(svc, "Hermes", "update_missing", "Google Sheets", f"Reports/{report_id}",
                         after="Report not found", result="not_found")
        return {"tab": "Reports", "id": report_id, "status": "not_found"}

    row_num, header, row = found
    current = {header[i]: row[i] if i < len(row) else "" for i in range(len(header))}
    before = json.dumps({k: current.get(k, "") for k in [
        "ReportType", "Summary", "PeopleServedEstimate", "ItemsDistributed",
        "FollowUpsNeeded", "SensitiveDetails", "PublicSummaryDraft", "PrivacyLevel",
        "Date", "Status", "NextAction", "LastUpdated", "SourceMessageLink",
    ]}, ensure_ascii=False)

    updates = {
        "SubmittedBy": submitted_by,
        "ReportType": report_type,
        "Summary": summary,
        "PeopleServedEstimate": people_served_estimate,
        "ItemsDistributed": items_distributed,
        "FollowUpsNeeded": followups_needed,
        "SensitiveDetails": sensitive_details,
        "PublicSummaryDraft": public_summary_draft,
        "PrivacyLevel": privacy_level,
        "Date": date,
        "NextAction": next_action,
        "Status": status,
        "Notes": notes,
        "PublicSummaryAllowed": public_summary_allowed,
        "SourceMessageLink": source_link,
    }
    for key, value in updates.items():
        if value is not None:
            current[key] = value
    current["LastUpdated"] = ts()
    after = json.dumps({k: current.get(k, "") for k in [
        "ReportType", "Summary", "PeopleServedEstimate", "ItemsDistributed",
        "FollowUpsNeeded", "SensitiveDetails", "PublicSummaryDraft", "PrivacyLevel",
        "Date", "Status", "NextAction", "LastUpdated", "SourceMessageLink",
    ]}, ensure_ascii=False)

    values = [current.get(h, "") for h in header]
    range_end = col(len(header))
    svc.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"Reports!A{row_num}:{range_end}{row_num}",
        valueInputOption="USER_ENTERED",
        body={"values": [values]},
    ).execute()

    write_audit_log(svc, "Hermes", "update", "Google Sheets", f"Reports/{report_id}",
                     before=before, after=after)
    return {"tab": "Reports", "id": report_id, "status": "updated"}


def add_task(
    svc,
    *,
    task_id: str = "",
    task_title: str = "",
    task_description: str = "",
    category: str = "general",
    priority: str = "medium",
    assigned_to: str = "",
    due_date: str = "",
    status: str = "new",
    source_link: str = "",
) -> dict:
    """Add a task row to the Tasks tab. Idempotent on TaskID."""
    ensure_header(svc, "Tasks")
    tid = task_id or gen_id("TASK")
    if _row_exists(svc, "Tasks", "TaskID", tid):
        write_audit_log(svc, "Hermes", "duplicate_skipped", "Google Sheets", f"Tasks/{tid}",
                         after=f"Task {tid} already exists; duplicate skipped")
        return {"tab": "Tasks", "id": tid, "status": "already_exists"}
    now_ts = ts()
    row = make_row("Tasks", {
        "TaskID": tid,
        "DateCreated": now_ts,
        "TaskTitle": task_title,
        "TaskDescription": task_description,
        "Category": category,
        "Priority": priority,
        "AssignedTo": assigned_to,
        "DueDate": due_date,
        "RelatedRequestID": "",
        "RelatedDonationID": "",
        "RelatedCalendarEventID": "",
        "Status": status,
        "Blocker": "",
        "NextAction": "",
        "CompletionReport": "",
        "LastUpdated": now_ts,
        "SourceMessageLink": source_link,
        "Notes": "",
    })
    result = append_row(svc, "Tasks", row)
    write_audit_log(svc, "Hermes", "create", "Google Sheets", f"Tasks/{tid}",
                     after=f"Task {tid} created: {task_title}")
    return {"tab": "Tasks", "id": tid, "status": "created", "api_result": result}


def update_task(
    svc,
    *,
    task_id: str,
    task_title: str | None = None,
    task_description: str | None = None,
    category: str | None = None,
    priority: str | None = None,
    assigned_to: str | None = None,
    due_date: str | None = None,
    status: str | None = None,
    next_action: str | None = None,
    source_link: str | None = None,
) -> dict:
    """Update an existing task row by TaskID."""
    ensure_header(svc, "Tasks")
    found = _find_row_by_id(svc, "Tasks", "TaskID", task_id)
    if not found:
        write_audit_log(svc, "Hermes", "update_missing", "Google Sheets", f"Tasks/{task_id}",
                         after="Task not found", result="not_found")
        return {"tab": "Tasks", "id": task_id, "status": "not_found"}

    row_num, header, row = found
    current = {header[i]: row[i] if i < len(row) else "" for i in range(len(header))}
    before = json.dumps({k: current.get(k, "") for k in [
        "TaskTitle", "TaskDescription", "Category", "Priority", "AssignedTo",
        "DueDate", "Status", "NextAction", "LastUpdated", "SourceMessageLink",
    ]}, ensure_ascii=False)

    updates = {
        "TaskTitle": task_title,
        "TaskDescription": task_description,
        "Category": category,
        "Priority": priority,
        "AssignedTo": assigned_to,
        "DueDate": due_date,
        "Status": status,
        "NextAction": next_action,
        "SourceMessageLink": source_link,
    }
    for key, value in updates.items():
        if value is not None:
            current[key] = value
    current["LastUpdated"] = ts()
    after = json.dumps({k: current.get(k, "") for k in [
        "TaskTitle", "TaskDescription", "Category", "Priority", "AssignedTo",
        "DueDate", "Status", "NextAction", "LastUpdated", "SourceMessageLink",
    ]}, ensure_ascii=False)

    values = [current.get(h, "") for h in header]
    range_end = col(len(header))
    svc.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"Tasks!A{row_num}:{range_end}{row_num}",
        valueInputOption="USER_ENTERED",
        body={"values": [values]},
    ).execute()

    write_audit_log(svc, "Hermes", "update", "Google Sheets", f"Tasks/{task_id}",
                     before=before, after=after)
    return {"tab": "Tasks", "id": task_id, "status": "updated"}


def update_inventory(
    svc,
    *,
    item_id: str = "",
    item_name: str = "",
    category: str = "other",
    quantity_on_hand: str = "",
    unit: str = "",
    minimum_needed: str = "",
    storage_location: str = "",
    condition: str = "",
    notes: str = "",
    needed_this_week: str = "",
    public_need_allowed: str = "",
    status: str = "",
    next_action: str = "",
    source_link: str = "",
    update_existing: bool = True,
) -> dict:
    """Upsert an inventory row. Creates new if ItemID is new; updates if exists."""
    ensure_header(svc, "Inventory")
    iid = item_id or gen_id("INV")
    existing = _find_row_by_id(svc, "Inventory", "ItemID", iid)

    if existing and update_existing:
        row_num, header, row = existing
        current = {header[i]: row[i] if i < len(row) else "" for i in range(len(header))}
        before = json.dumps({k: current.get(k, "") for k in [
            "ItemName", "Category", "QuantityOnHand", "Unit", "MinimumNeeded",
            "StorageLocation", "Condition", "NeededThisWeek", "PublicNeedAllowed",
            "Notes", "Status", "NextAction", "LastUpdated", "SourceMessageLink",
        ]}, ensure_ascii=False)

        updates = {
            "ItemName": item_name,
            "Category": category,
            "QuantityOnHand": quantity_on_hand,
            "Unit": unit,
            "MinimumNeeded": minimum_needed,
            "StorageLocation": storage_location,
            "Condition": condition,
            "NeededThisWeek": needed_this_week,
            "PublicNeedAllowed": public_need_allowed,
            "Notes": notes,
            "Status": status,
            "NextAction": next_action,
            "SourceMessageLink": source_link,
        }
        for key, value in updates.items():
            if value is not None and value != "":
                current[key] = value
        current["LastUpdated"] = ts()
        current["LastUpdatedBy"] = "Hermes"
        after = json.dumps({k: current.get(k, "") for k in [
            "ItemName", "Category", "QuantityOnHand", "Unit", "MinimumNeeded",
            "StorageLocation", "Condition", "NeededThisWeek", "PublicNeedAllowed",
            "Notes", "Status", "NextAction", "LastUpdated", "SourceMessageLink",
        ]}, ensure_ascii=False)

        values = [current.get(h, "") for h in header]
        range_end = col(len(header))
        svc.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"Inventory!A{row_num}:{range_end}{row_num}",
            valueInputOption="USER_ENTERED",
            body={"values": [values]},
        ).execute()

        write_audit_log(svc, "Hermes", "update", "Google Sheets", f"Inventory/{iid}",
                         before=before, after=after)
        return {"tab": "Inventory", "id": iid, "status": "updated"}

    # Create new row
    now_ts = ts()
    row = make_row("Inventory", {
        "ItemID": iid,
        "ItemName": item_name,
        "Category": category,
        "QuantityOnHand": quantity_on_hand,
        "Unit": unit,
        "MinimumNeeded": minimum_needed,
        "StorageLocation": storage_location,
        "Condition": condition,
        "LastCounted": now_ts,
        "LastUpdatedBy": "Hermes",
        "NeededThisWeek": needed_this_week,
        "PublicNeedAllowed": public_need_allowed,
        "Notes": notes,
        "Status": status or "needs-info",
        "NextAction": next_action or "review",
        "LastUpdated": now_ts,
        "SourceMessageLink": source_link,
    })
    result = append_row(svc, "Inventory", row)
    write_audit_log(svc, "Hermes", "create", "Google Sheets", f"Inventory/{iid}",
                     after=f"Inventory {iid} created: {item_name} qty={quantity_on_hand}")
    return {"tab": "Inventory", "id": iid, "status": "created", "api_result": result}


def _insert_google_calendar_event(
    svc_cal,
    *,
    title: str,
    description: str = "",
    location: str = "",
    start: datetime,
    end: datetime,
) -> dict:
    """Insert a single event into Google Calendar; return the created event dict.

    Shared by create_calendar_event (EVENT-001) and create_calendar_event_from_draft
    (EVENT-002). Callers own CalendarLog row creation/update + audit logging, so that
    EVENT-002 updates the SAME draft row instead of appending a second CalendarLog row.
    """
    event_body = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
        "end": {"dateTime": end.isoformat(), "timeZone": "UTC"},
    }
    if location:
        event_body["location"] = location
    return svc_cal.events().insert(calendarId=CALENDAR_ID, body=event_body).execute()


def create_calendar_event(
    svc_cal,
    svc_sheets,
    *,
    event_title: str = "",
    event_type: str = "test",
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    description: str = "",
    location: str = "",
    private_location: str = "",
    related_task_id: str = "",
    related_request_id: str = "",
    related_donation_id: str = "",
) -> dict:
    """Create a real Google Calendar event and log it in CalendarLog. Idempotent on event title."""
    start = start_time or now_utc()
    end = end_time or (start + timedelta(hours=1))
    title = event_title or f"Event {gen_id('EVT')}"

    # Check for existing event with same title
    existing_id = _calendar_event_exists(svc_cal, title)
    if existing_id:
        write_audit_log(svc_sheets, "Hermes", "duplicate_skipped", "Google Calendar",
                         f"Calendar/{existing_id}",
                         after=f"Calendar event '{title}' already exists (ID: {existing_id}); duplicate skipped")
        return {"tab": "CalendarLog", "calendar_id": existing_id, "status": "already_exists"}

    # Create the calendar event
    created = _insert_google_calendar_event(
        svc_cal,
        title=title,
        description=description,
        location=location if not private_location else "",
        start=start,
        end=end,
    )
    cal_event_id = created.get("id", "")

    # Write to CalendarLog sheet
    cl_row = make_row("CalendarLog", {
        "CalendarEventID": cal_event_id,
        "EventTitle": title,
        "EventType": event_type,
        "StartDateTime": start.isoformat(),
        "EndDateTime": end.isoformat(),
        "Location": location if not private_location else "",
        "PrivateLocation": private_location,
        "Description": description,
        "RelatedTaskID": related_task_id,
        "RelatedRequestID": related_request_id,
        "RelatedDonationID": related_donation_id,
        "Status": "confirmed",
        "CreatedBy": "Hermes",
        "LastUpdated": ts(),
    })
    ensure_header(svc_sheets, "CalendarLog")
    append_row(svc_sheets, "CalendarLog", cl_row)

    # Audit
    write_audit_log(svc_sheets, "Hermes", "create", "Google Calendar",
                     f"Calendar/{cal_event_id}",
                     after=f"Calendar event '{title}' created (ID: {cal_event_id})")

    return {"tab": "CalendarLog", "calendar_id": cal_event_id, "status": "created", "api_result": created}


# ── EVENT-002: durable event-draft backend ──────────────────────────────────

def _normalize_event_draft_fields(**kwargs) -> dict:
    """Build a CalendarLog mapping from EVENT-002 draft keyword args.

    Only fields that are part of the 24-column schema and have a non-None value
    are returned. Empty string / None mean 'leave as-is or use default' and are
    skipped here so callers can decide default-vs-preserve semantics.
    """
    mapping: dict[str, Any] = {}
    field_to_header = {
        "event_draft_id": "EventDraftID",
        "event_title": "EventTitle",
        "event_type": "EventType",
        "start_time": "StartDateTime",
        "end_time": "EndDateTime",
        "description": "Description",
        "location": "Location",
        "private_location": "PrivateLocation",
        "attendees": "Attendees",
        "related_task_id": "RelatedTaskID",
        "related_request_id": "RelatedRequestID",
        "related_donation_id": "RelatedDonationID",
        "privacy_level": "PrivacyLevel",
        "public_calendar_allowed": "PublicCalendarAllowed",
        "public_title": "PublicTitle",
        "public_description": "PublicDescription",
        "public_location": "PublicLocation",
        "approval_status": "ApprovalStatus",
        "status": "Status",
        "source_link": "SourceMessageLink",
        "notes": "Notes",
    }
    for kw, header in field_to_header.items():
        value = kwargs.get(kw)
        if value is None or value == "":
            continue
        mapping[header] = value
    return mapping


def upsert_event_draft(
    svc,
    *,
    event_draft_id: str = "",
    event_title: str = "",
    event_type: str = "event",
    start_time: str = "",
    end_time: str = "",
    description: str = "",
    location: str = "",
    private_location: str = "",
    attendees: str = "",
    related_task_id: str = "",
    related_request_id: str = "",
    related_donation_id: str = "",
    privacy_level: str = "",
    public_calendar_allowed: str = "",
    public_title: str = "",
    public_description: str = "",
    public_location: str = "",
    approval_status: str = "",
    status: str = "",
    source_link: str = "",
    notes: str = "",
) -> dict:
    """Upsert an event draft into the CalendarLog tab.

    - Generates EVT-XXXXXXXX when event_draft_id is absent.
    - Appends a new draft row when EventDraftID is new; updates the same row when present.
    - Never creates a second row for the same EventDraftID.
    - Preserves existing values when an update param is empty/omitted.
    - CalendarEventID stays blank during draft create/normal update.
    - Default new draft: PrivacyLevel=private-review, PublicCalendarAllowed=no,
      ApprovalStatus=needs-info, Status=needs-info, CreatedBy=Hermes.
    - Updates LastUpdated on every write.
    - Returns {'status': 'created'} or {'status': 'updated'}.
    - Writes AuditLog create/update with TargetItem CalendarLog/<EVT>.
    """
    ensure_header(svc, "CalendarLog")
    draft_id = event_draft_id or gen_id("EVT")

    existing = _find_row_by_id(svc, "CalendarLog", "EventDraftID", draft_id)
    now_ts = ts()

    if existing:
        row_num, header, row = existing
        current = {header[i]: row[i] if i < len(row) else "" for i in range(len(header))}

        before = json.dumps({
            k: current.get(k, "")
            for k in ["EventTitle", "EventType", "StartDateTime", "EndDateTime", "Description",
                       "Location", "PrivateLocation", "Attendees", "PrivacyLevel",
                       "PublicCalendarAllowed", "PublicTitle", "PublicDescription", "PublicLocation",
                       "ApprovalStatus", "Status", "LastUpdated"]
        }, ensure_ascii=False)

        updates = _normalize_event_draft_fields(
            event_title=event_title, event_type=event_type, start_time=start_time, end_time=end_time,
            description=description, location=location, private_location=private_location,
            attendees=attendees, related_task_id=related_task_id, related_request_id=related_request_id,
            related_donation_id=related_donation_id, privacy_level=privacy_level,
            public_calendar_allowed=public_calendar_allowed, public_title=public_title,
            public_description=public_description, public_location=public_location,
            approval_status=approval_status, status=status, source_link=source_link, notes=notes,
        )
        # Never overwrite CalendarEventID on a normal draft update; keep it blank.
        updates.pop("CalendarEventID", None)
        for key, value in updates.items():
            current[key] = value
        current["LastUpdated"] = now_ts

        after = json.dumps({
            k: current.get(k, "")
            for k in ["EventTitle", "EventType", "StartDateTime", "EndDateTime", "Description",
                       "Location", "PrivateLocation", "Attendees", "PrivacyLevel",
                       "PublicCalendarAllowed", "PublicTitle", "PublicDescription", "PublicLocation",
                       "ApprovalStatus", "Status", "LastUpdated"]
        }, ensure_ascii=False)

        values = [current.get(h, "") for h in header]
        range_end = col(len(header))
        svc.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"CalendarLog!A{row_num}:{range_end}{row_num}",
            valueInputOption="USER_ENTERED",
            body={"values": [values]},
        ).execute()

        write_audit_log(svc, "Hermes", "update", "Google Sheets", f"CalendarLog/{draft_id}",
                         before=before, after=after)
        return {"tab": "CalendarLog", "id": draft_id, "status": "updated"}

    # New draft row.
    now_ts = ts()
    row = make_row("CalendarLog", {
        "EventDraftID": draft_id,
        "EventTitle": event_title,
        "EventType": event_type,
        "StartDateTime": start_time,
        "EndDateTime": end_time,
        "Location": location,
        "PrivateLocation": private_location,
        "Description": description,
        "Attendees": attendees,
        "RelatedTaskID": related_task_id,
        "RelatedRequestID": related_request_id,
        "RelatedDonationID": related_donation_id,
        "Status": status or "needs-info",
        "CreatedBy": "Hermes",
        "LastUpdated": now_ts,
        "PrivacyLevel": privacy_level or "private-review",
        "PublicCalendarAllowed": public_calendar_allowed or "no",
        "PublicTitle": public_title,
        "PublicDescription": public_description,
        "PublicLocation": public_location,
        "ApprovalStatus": approval_status or "needs-info",
        "SourceMessageLink": source_link,
        "Notes": notes,
    })
    append_row(svc, "CalendarLog", row)
    write_audit_log(svc, "Hermes", "create", "Google Sheets", f"CalendarLog/{draft_id}",
                     after=f"Event draft {draft_id} created: {event_title}")
    return {"tab": "CalendarLog", "id": draft_id, "status": "created"}


def update_event_draft(
    svc,
    *,
    event_draft_id: str,
    event_title: str | None = None,
    event_type: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    description: str | None = None,
    location: str | None = None,
    private_location: str | None = None,
    attendees: str | None = None,
    related_task_id: str | None = None,
    related_request_id: str | None = None,
    related_donation_id: str | None = None,
    privacy_level: str | None = None,
    public_calendar_allowed: str | None = None,
    public_title: str | None = None,
    public_description: str | None = None,
    public_location: str | None = None,
    approval_status: str | None = None,
    status: str | None = None,
    source_link: str | None = None,
    notes: str | None = None,
) -> dict:
    """Strict update of an existing event draft.

    - Returns {'status': 'not_found'} for an unknown EventDraftID (no silent creation).
    - Applies partial non-empty updates; empty/None params are preserved.
    - Preserves CalendarEventID.
    - Writes before/after audit.
    - Returns {'status': 'updated'} on success.
    """
    ensure_header(svc, "CalendarLog")
    found = _find_row_by_id(svc, "CalendarLog", "EventDraftID", event_draft_id)
    if not found:
        write_audit_log(svc, "Hermes", "update_missing", "Google Sheets", f"CalendarLog/{event_draft_id}",
                         after="Event draft not found", result="not_found")
        return {"tab": "CalendarLog", "id": event_draft_id, "status": "not_found"}

    row_num, header, row = found
    current = {header[i]: row[i] if i < len(row) else "" for i in range(len(header))}

    before = json.dumps({
        k: current.get(k, "")
        for k in ["EventTitle", "EventType", "StartDateTime", "EndDateTime", "Description",
                   "Location", "PrivateLocation", "Attendees", "PrivacyLevel",
                   "PublicCalendarAllowed", "PublicTitle", "PublicDescription", "PublicLocation",
                   "ApprovalStatus", "Status", "CalendarEventID", "LastUpdated"]
    }, ensure_ascii=False)

    updates = {
        "EventTitle": event_title,
        "EventType": event_type,
        "StartDateTime": start_time,
        "EndDateTime": end_time,
        "Description": description,
        "Location": location,
        "PrivateLocation": private_location,
        "Attendees": attendees,
        "RelatedTaskID": related_task_id,
        "RelatedRequestID": related_request_id,
        "RelatedDonationID": related_donation_id,
        "PrivacyLevel": privacy_level,
        "PublicCalendarAllowed": public_calendar_allowed,
        "PublicTitle": public_title,
        "PublicDescription": public_description,
        "PublicLocation": public_location,
        "ApprovalStatus": approval_status,
        "Status": status,
        "SourceMessageLink": source_link,
        "Notes": notes,
    }
    for key, value in updates.items():
        if value is not None and value != "":
            current[key] = value
    current["LastUpdated"] = ts()

    after = json.dumps({
        k: current.get(k, "")
        for k in ["EventTitle", "EventType", "StartDateTime", "EndDateTime", "Description",
                   "Location", "PrivateLocation", "Attendees", "PrivacyLevel",
                   "PublicCalendarAllowed", "PublicTitle", "PublicDescription", "PublicLocation",
                   "ApprovalStatus", "Status", "CalendarEventID", "LastUpdated"]
    }, ensure_ascii=False)

    values = [current.get(h, "") for h in header]
    range_end = col(len(header))
    svc.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"CalendarLog!A{row_num}:{range_end}{row_num}",
        valueInputOption="USER_ENTERED",
        body={"values": [values]},
    ).execute()

    write_audit_log(svc, "Hermes", "update", "Google Sheets", f"CalendarLog/{event_draft_id}",
                     before=before, after=after)
    return {"tab": "CalendarLog", "id": event_draft_id, "status": "updated"}


def _as_timezone_aware(start_time, end_time):
    """Validate + normalize start/end to timezone-aware datetimes.

    Accepts datetime objects (must be tz-aware) or ISO strings WITH an offset.
    Rejects naive datetimes and naive ISO strings (e.g. '2026-07-12T09:00:00') — they
    must not silently become UTC. Returns (start_dt, end_dt) or raises ValueError.

    Uses stdlib only (no external iso8601 dependency). Python 3.11+ fromisoformat
    parses offset/designator strings; we also accept a trailing 'Z'.
    """
    from datetime import datetime as _dt

    def _parse(value):
        if isinstance(value, datetime):
            dt = value
        else:
            if not isinstance(value, str) or value.strip() == "":
                raise ValueError("empty datetime")
            s = value.strip()
            # Require an offset or a 'Z' designator. Naive 'T...:' without offset is rejected.
            if "T" in s and not (s.endswith("Z") or "+" in s[10:] or "-" in s[10:]):
                raise ValueError(f"naive datetime (no offset): {s}")
            candidate = s
            if candidate.endswith("Z"):
                candidate = candidate[:-1] + "+00:00"
            dt = _dt.fromisoformat(candidate)
        if dt.tzinfo is None:
            raise ValueError(f"naive datetime rejected (no tz): {value}")
        return dt

    start_dt = _parse(start_time)
    if end_time:
        end_dt = _parse(end_time)
    else:
        end_dt = start_dt + timedelta(hours=1)
    return start_dt, end_dt


def create_calendar_event_from_draft(
    svc_cal,
    svc_sheets,
    *,
    event_draft_id: str,
) -> dict:
    """Promote an APPROVED event draft to a real Google Calendar event. Fake-testable only.

    Blocks unless: EventDraftID exists, CalendarEventID blank, EventTitle nonempty,
    StartDateTime is timezone-aware / offset ISO, EndDateTime safe or defaults +1h,
    ApprovalStatus=approved, Status=ready. Does NOT require PublicCalendarAllowed=yes.

    On success:
    - Creates ONE calendar event via private operational fields (EventTitle, Description,
      Location). The calendar title is prefixed 'EVT-XXXXXXXX — <title>'.
    - Never uses PublicTitle as the operational calendar title.
    - Updates the SAME CalendarLog row with CalendarEventID, ApprovalStatus=created,
      Status=confirmed, LastUpdated.
    - Writes one AuditLog row (action create-calendar-event).
    - Returns {'status': 'created', 'event_draft_id', 'calendar_id'}.

    Idempotency: if CalendarEventID already populated, returns
    {'status': 'already_created', 'calendar_id'} WITHOUT calling insert again — exactly
    one CalendarLog row, exactly one insert on retry.
    """
    ensure_header(svc_sheets, "CalendarLog")
    found = _find_row_by_id(svc_sheets, "CalendarLog", "EventDraftID", event_draft_id)
    if not found:
        write_audit_log(svc_sheets, "Hermes", "create_calendar_event_blocked", "Google Calendar",
                         f"CalendarLog/{event_draft_id}", after="Draft not found", result="blocked")
        return {"tab": "CalendarLog", "id": event_draft_id, "status": "not_found", "calendar_id": ""}

    row_num, header, row = found
    current = {header[i]: row[i] if i < len(row) else "" for i in range(len(header))}

    # Idempotency: already created -> do not insert again.
    existing_cal_id = current.get("CalendarEventID", "")
    if existing_cal_id:
        write_audit_log(svc_sheets, "Hermes", "create_calendar_event_idempotent", "Google Calendar",
                         f"CalendarLog/{event_draft_id}",
                         after=f"Event already created (ID: {existing_cal_id}); insert skipped")
        return {"tab": "CalendarLog", "id": event_draft_id, "status": "already_created",
                "calendar_id": existing_cal_id}

    # Block conditions.
    title = current.get("EventTitle", "").strip()
    if not title:
        write_audit_log(svc_sheets, "Hermes", "create_calendar_event_blocked", "Google Calendar",
                         f"CalendarLog/{event_draft_id}", after="Missing EventTitle", result="blocked")
        return {"tab": "CalendarLog", "id": event_draft_id, "status": "blocked", "calendar_id": ""}

    start_raw = current.get("StartDateTime", "")
    try:
        start_dt, end_dt = _as_timezone_aware(start_raw, current.get("EndDateTime", ""))
    except ValueError as exc:
        write_audit_log(svc_sheets, "Hermes", "create_calendar_event_blocked", "Google Calendar",
                         f"CalendarLog/{event_draft_id}",
                         after=f"Invalid start/end datetime: {exc}", result="blocked")
        return {"tab": "CalendarLog", "id": event_draft_id, "status": "blocked", "calendar_id": ""}

    if current.get("ApprovalStatus", "").strip() != "approved":
        write_audit_log(svc_sheets, "Hermes", "create_calendar_event_blocked", "Google Calendar",
                         f"CalendarLog/{event_draft_id}",
                         after=f"ApprovalStatus not approved: {current.get('ApprovalStatus', '')}",
                         result="blocked")
        return {"tab": "CalendarLog", "id": event_draft_id, "status": "blocked", "calendar_id": ""}

    if current.get("Status", "").strip() != "ready":
        write_audit_log(svc_sheets, "Hermes", "create_calendar_event_blocked", "Google Calendar",
                         f"CalendarLog/{event_draft_id}",
                         after=f"Status not ready: {current.get('Status', '')}", result="blocked")
        return {"tab": "CalendarLog", "id": event_draft_id, "status": "blocked", "calendar_id": ""}

    # Operational fields are the PRIVATE draft fields, never PublicTitle.
    operational_title = f"{event_draft_id} — {title}"
    description = current.get("Description", "")
    location = current.get("Location", "") if current.get("PrivateLocation", "") else current.get("Location", "")
    private_location = current.get("PrivateLocation", "")

    created = _insert_google_calendar_event(
        svc_cal,
        title=operational_title,
        description=description,
        location=location if not private_location else "",
        start=start_dt,
        end=end_dt,
    )
    cal_event_id = created.get("id", "")

    # Update the SAME CalendarLog row; no second append.
    current["CalendarEventID"] = cal_event_id
    current["ApprovalStatus"] = "created"
    current["Status"] = "confirmed"
    current["LastUpdated"] = ts()
    values = [current.get(h, "") for h in header]
    range_end = col(len(header))
    svc_sheets.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"CalendarLog!A{row_num}:{range_end}{row_num}",
        valueInputOption="USER_ENTERED",
        body={"values": [values]},
    ).execute()

    write_audit_log(svc_sheets, "Hermes", "create-calendar-event", "Google Calendar",
                     f"CalendarLog/{event_draft_id}",
                     after=f"Calendar event created from draft {event_draft_id} (ID: {cal_event_id})")

    return {"tab": "CalendarLog", "id": event_draft_id, "status": "created", "calendar_id": cal_event_id}


# ── CLI test mode ──────────────────────────────────────────────────────────

def run_test_write() -> int:
    """Create safe fake test records to prove write capability."""
    print("=== Non-Profit Hermes Ops — Test Write ===\n")

    c = get_creds()
    svc = sheets(c)
    svc_cal = calendar(c)

    now = now_utc()
    tomorrow = now + timedelta(days=1)
    next_week = now + timedelta(days=7)

    results = []

    # 1. Add a request
    r = add_request(
        svc,
        request_id="REQ-WRITE-TEST-001",
        source="Hermes test",
        submitted_by="Hermes (test-write)",
        person_or_group="Test Person (safe fake)",
        need_category="clothing",
        need_description="Safe fake test request for write capability verification",
        quantity="1",
        urgency="low",
        needed_by=tomorrow.strftime("%Y-%m-%d"),
        privacy_level="board-visible",
        status="new",
        next_action="Review by Hermes",
        notes="TEST RECORD — no real data",
    )
    results.append(("Request", r["id"], "Requests tab"))
    print(f"  ✓ Request {r['id']} written to Requests tab")

    # 2. Add a donation
    d = add_donation(
        svc,
        donation_id="DON-WRITE-TEST-001",
        donor_name="Test Donor (safe fake)",
        donation_type="clothing",
        item_description="Safe fake test donation for write capability verification",
        quantity="5",
        condition="new",
        pickup_or_dropoff="drop-off",
        location="Test Location (safe fake — not real)",
        status="new",
    )
    results.append(("Donation", d["id"], "Donations tab"))
    print(f"  ✓ Donation {d['id']} written to Donations tab")

    # 3. Add a report
    rp = add_report(
        svc,
        report_id="REP-WRITE-TEST-001",
        submitted_by="Hermes (test-write)",
        report_type="test",
        summary="Safe fake test report for write capability verification",
        privacy_level="board-visible",
        sensitive_details="",  # explicitly empty — no sensitive data
    )
    results.append(("Report", rp["id"], "Reports tab"))
    print(f"  ✓ Report {rp['id']} written to Reports tab")

    # 4. Add a task
    t = add_task(
        svc,
        task_id="TASK-WRITE-TEST-001",
        task_title="Safe fake test task",
        task_description="Verify task write capability in Non-Profit Hermes",
        category="general",
        priority="low",
        assigned_to="Hermes (test)",
        due_date=tomorrow.strftime("%Y-%m-%d"),
        status="new",
    )
    results.append(("Task", t["id"], "Tasks tab"))
    print(f"  ✓ Task {t['id']} written to Tasks tab")

    # 5. Update inventory
    inv = update_inventory(
        svc,
        item_id="INV-WRITE-TEST-001",
        item_name="Safe fake test socks",
        category="socks",
        quantity_on_hand="50",
        unit="pairs",
        minimum_needed="10",
        storage_location="Test shelf (safe fake)",
        condition="new",
        notes="TEST RECORD — no real inventory data",
    )
    results.append(("Inventory", inv["id"], "Inventory tab"))
    print(f"  ✓ Inventory {inv['id']} written to Inventory tab")

    # 6. Create calendar event
    cal = create_calendar_event(
        svc_cal,
        svc,
        event_title="CAL-WRITE-TEST-001 — Safe write test event",
        event_type="test",
        start_time=now + timedelta(hours=2),
        end_time=now + timedelta(hours=3),
        description="Safe fake test calendar event for write capability verification. Created by Non-Profit Hermes test-write.",
        location="",
        private_location="",
        related_request_id="REQ-WRITE-TEST-001",
        related_task_id="TASK-WRITE-TEST-001",
    )
    results.append(("Calendar", cal["calendar_id"], "CalendarLog tab + Google Calendar"))
    print(f"  ✓ Calendar event {cal['calendar_id']} created in Google Calendar + CalendarLog")

    # Summary
    print(f"\n=== Test write complete — {len(results)} operations ===")
    for label, op_id, target in results:
        print(f"  {label}: {op_id} → {target}")

    print("\nNow run: python scripts/sync_approved_safe_data.py")
    print("to refresh the docs/ site with the new test records.\n")

    # Return results as JSON too
    print(json.dumps({"operations": len(results), "results": results}, indent=2))
    return 0


# ── Main ────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Non-Profit Hermes Ops Backend")
    parser.add_argument("--test-write", action="store_true", help="Run safe fake test write")
    args = parser.parse_args()

    if args.test_write:
        return run_test_write()

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())