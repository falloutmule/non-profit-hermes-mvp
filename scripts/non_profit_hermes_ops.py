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

# ── Shared config (same as sync_approved_safe_data.py) ──────────────────────

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

# ── Column headers per tab (from MVP data model) ────────────────────────────

HEADERS: dict[str, list[str]] = {
    "Requests": [
        "RequestID", "DateReceived", "Source", "SubmittedBy", "PersonOrGroup",
        "ContactMethod", "NeedCategory", "NeedDescription", "Quantity",
        "LocationPrivate", "LocationPublicSafe", "Urgency", "NeededBy",
        "ConsentToRecord", "ConsentToShare", "PrivacyLevel", "AssignedTo",
        "Status", "NextAction", "CalendarEventID", "RelatedInventoryItem",
        "Notes", "CreatedBy", "LastUpdated", "SourceMessageLink",
    ],
    "Donations": [
        "DonationID", "DateOffered", "DonorName", "DonorContact",
        "DonationType", "ItemDescription", "Quantity", "Condition",
        "PickupOrDropoff", "Location", "AvailableDate", "StorageNeeded",
        "MatchesCurrentNeed", "AssignedPickupVolunteer", "Status",
        "ReceiptNeeded", "ThankYouNeeded", "ConsentToPublicThanks",
        "Notes", "SourceMessageLink",
    ],
    "Reports": [
        "ReportID", "Date", "SubmittedBy", "ReportType", "Summary",
        "PeopleServedEstimate", "ItemsDistributed", "Incidents",
        "FollowUpsNeeded", "SensitiveDetails", "PublicSummaryDraft",
        "PrivacyLevel", "RelatedTasks", "RelatedRequests", "RelatedDonations",
        "PhotosAttached", "SourceMessageLink",
    ],
    "Tasks": [
        "TaskID", "DateCreated", "TaskTitle", "TaskDescription", "Category",
        "Priority", "AssignedTo", "DueDate", "RelatedRequestID",
        "RelatedDonationID", "RelatedCalendarEventID", "Status", "Blocker",
        "NextAction", "CompletionReport", "LastUpdated",
    ],
    "Inventory": [
        "ItemID", "ItemName", "Category", "QuantityOnHand", "Unit",
        "MinimumNeeded", "StorageLocation", "Condition", "LastCounted",
        "LastUpdatedBy", "NeededThisWeek", "PublicNeedAllowed", "Notes",
    ],
    "CalendarLog": [
        "CalendarEventID", "EventTitle", "EventType", "StartDateTime",
        "EndDateTime", "Location", "PrivateLocation", "Description",
        "Attendees", "RelatedTaskID", "RelatedRequestID", "RelatedDonationID",
        "Status", "CreatedBy", "LastUpdated",
    ],
    "AuditLog": [
        "AuditID", "Timestamp", "Actor", "Action", "TargetSystem",
        "TargetItem", "Before", "After", "Result", "Error", "SourceMessageLink",
    ],
}

# ── Helpers ─────────────────────────────────────────────────────────────────

AUDIT_HEADERS = HEADERS["AuditLog"]


def col(n: int) -> str:
    """Convert 1-indexed column number to A1 notation."""
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


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


# ── Primary operations ─────────────────────────────────────────────────────

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
    notes: str = "",
    source_link: str = "",
) -> dict:
    """Add a donation row to the Donations tab. Idempotent on DonationID."""
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
        "Notes": notes,
        "SourceMessageLink": source_link,
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
    notes: str | None = None,
    source_link: str | None = None,
) -> dict:
    """Update an existing donation row by DonationID."""
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
        "ConsentToPublicThanks", "Notes", "LastUpdated", "SourceMessageLink",
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
        "ConsentToPublicThanks", "Notes", "LastUpdated", "SourceMessageLink",
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
) -> dict:
    """Add a report row to the Reports tab. Idempotent on ReportID."""
    rid = report_id or gen_id("REP")
    if _row_exists(svc, "Reports", "ReportID", rid):
        write_audit_log(svc, "Hermes", "duplicate_skipped", "Google Sheets", f"Reports/{rid}",
                         after=f"Report {rid} already exists; duplicate skipped")
        return {"tab": "Reports", "id": rid, "status": "already_exists"}
    now_ts = ts()
    row = make_row("Reports", {
        "ReportID": rid,
        "Date": now_ts,
        "SubmittedBy": submitted_by,
        "ReportType": report_type,
        "Summary": summary,
        "SensitiveDetails": sensitive_details,
        "PublicSummaryDraft": summary,
        "PrivacyLevel": privacy_level,
        "SourceMessageLink": source_link,
    })
    result = append_row(svc, "Reports", row)
    write_audit_log(svc, "Hermes", "create", "Google Sheets", f"Reports/{rid}",
                     after=f"Report {rid} created: {summary}")
    return {"tab": "Reports", "id": rid, "status": "created", "api_result": result}

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
        "Status": status,
        "LastUpdated": now_ts,
        "SourceMessageLink": source_link,
    })
    result = append_row(svc, "Tasks", row)
    write_audit_log(svc, "Hermes", "create", "Google Sheets", f"Tasks/{tid}",
                     after=f"Task {tid} created: {task_title}")
    return {"tab": "Tasks", "id": tid, "status": "created", "api_result": result}


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
) -> dict:
    """Add/update an inventory row in the Inventory tab. Idempotent on ItemID."""
    iid = item_id or gen_id("INV")
    if _row_exists(svc, "Inventory", "ItemID", iid):
        write_audit_log(svc, "Hermes", "duplicate_skipped", "Google Sheets", f"Inventory/{iid}",
                         after=f"Inventory {iid} already exists; duplicate skipped")
        return {"tab": "Inventory", "id": iid, "status": "already_exists"}
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
        "Notes": notes,
    })
    result = append_row(svc, "Inventory", row)
    write_audit_log(svc, "Hermes", "update", "Google Sheets", f"Inventory/{iid}",
                     after=f"Inventory {iid} updated: {item_name} qty={quantity_on_hand}")
    return {"tab": "Inventory", "id": iid, "status": "created", "api_result": result}


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
    event_body = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
        "end": {"dateTime": end.isoformat(), "timeZone": "UTC"},
    }
    if location:
        event_body["location"] = location

    created = svc_cal.events().insert(calendarId=CALENDAR_ID, body=event_body).execute()
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
    append_row(svc_sheets, "CalendarLog", cl_row)

    # Audit
    write_audit_log(svc_sheets, "Hermes", "create", "Google Calendar",
                     f"Calendar/{cal_event_id}",
                     after=f"Calendar event '{title}' created (ID: {cal_event_id})")

    return {"tab": "CalendarLog", "calendar_id": cal_event_id, "status": "created", "api_result": created}


# ── CLI test mode ───────────────────────────────────────────────────────────

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
    parser = argparse.ArgumentParser(description="Non-Profit Hermes backend write operations")
    parser.add_argument("--test-write", action="store_true", help="Run safe fake test writes")
    args = parser.parse_args()

    if args.test_write:
        return run_test_write()

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
