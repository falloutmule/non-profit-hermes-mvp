"""
Canonical shared schema for Non-Profit Hermes MVP.

This module is the SINGLE SOURCE OF TRUTH for all Sheet column headers,
primary keys, publication gates, and privacy policies.

Both non_profit_hermes_ops.py (write-side) and sync_approved_safe_data.py (read/export-side)
MUST import from here. No duplicate HEADERS maps allowed.
"""

from __future__ import annotations

from typing import Final

# ── Column headers per tab ────────────────────────────────────────────────────

# Order is authoritative. New columns MUST be appended, never inserted or reordered.
# After appending to this module, call ensure_header() for the affected tabs
# to update the live Sheet header row.

HEADERS: Final[dict[str, list[str]]] = {
    "Requests": [
        "RequestID",
        "DateReceived",
        "Source",
        "SubmittedBy",
        "PersonOrGroup",
        "ContactMethod",
        "NeedCategory",
        "NeedDescription",
        "Quantity",
        "LocationPrivate",
        "LocationPublicSafe",
        "Urgency",
        "NeededBy",
        "ConsentToRecord",
        "ConsentToShare",
        "PrivacyLevel",
        "AssignedTo",
        "Status",
        "NextAction",
        "CalendarEventID",
        "RelatedInventoryItem",
        "Notes",
        "CreatedBy",
        "LastUpdated",
        "SourceMessageLink",
    ],
    "Donations": [
        "DonationID",
        "DateOffered",
        "DonorName",
        "DonorContact",
        "DonationType",
        "ItemDescription",
        "Quantity",
        "Condition",
        "PickupOrDropoff",
        "Location",
        "AvailableDate",
        "StorageNeeded",
        "MatchesCurrentNeed",
        "AssignedPickupVolunteer",
        "Status",
        "ReceiptNeeded",
        "ThankYouNeeded",
        "ConsentToPublicThanks",
        "NextAction",
        "Notes",
        "SourceMessageLink",
        # NEW columns appended for CLEANUP-002
        "PrivacyLevel",
        "PublicListingAllowed",
        "LastUpdated",
    ],
    "Reports": [
        "ReportID",
        "Date",
        "SubmittedBy",
        "ReportType",
        "Summary",
        "PeopleServedEstimate",
        "ItemsDistributed",
        "Incidents",
        "FollowUpsNeeded",
        "SensitiveDetails",
        "PublicSummaryDraft",
        "PrivacyLevel",
        "RelatedTasks",
        "RelatedRequests",
        "RelatedDonations",
        "PhotosAttached",
        "Status",
        "NextAction",
        "Notes",
        "LastUpdated",
        "SourceMessageLink",
        # NEW column appended for CLEANUP-002
        "PublicSummaryAllowed",
    ],
    "Tasks": [
        "TaskID",
        "DateCreated",
        "TaskTitle",
        "TaskDescription",
        "Category",
        "Priority",
        "AssignedTo",
        "DueDate",
        "RelatedRequestID",
        "RelatedDonationID",
        "RelatedCalendarEventID",
        "Status",
        "Blocker",
        "NextAction",
        "CompletionReport",
        "LastUpdated",
        "SourceMessageLink",
        "Notes",
    ],
    "Inventory": [
        "ItemID",
        "ItemName",
        "Category",
        "QuantityOnHand",
        "Unit",
        "MinimumNeeded",
        "StorageLocation",
        "Condition",
        "LastCounted",
        "LastUpdatedBy",
        "NeededThisWeek",
        "PublicNeedAllowed",
        "Notes",
        "Status",
        "NextAction",
        "LastUpdated",
        "SourceMessageLink",
    ],
    "CalendarLog": [
        "CalendarEventID",
        "EventTitle",
        "EventType",
        "StartDateTime",
        "EndDateTime",
        "Location",
        "PrivateLocation",
        "Description",
        "Attendees",
        "RelatedTaskID",
        "RelatedRequestID",
        "RelatedDonationID",
        "Status",
        "CreatedBy",
        "LastUpdated",
        "EventDraftID",
        "PrivacyLevel",
        "PublicCalendarAllowed",
        "PublicTitle",
        "PublicDescription",
        "PublicLocation",
        "ApprovalStatus",
        "SourceMessageLink",
        "Notes",
    ],
    "AuditLog": [
        "AuditID",
        "Timestamp",
        "Actor",
        "Action",
        "TargetSystem",
        "TargetItem",
        "Before",
        "After",
        "Result",
        "Error",
        "SourceMessageLink",
    ],
}

# ── Primary keys per tab (for deduplication) ──────────────────────────────────

PRIMARY_KEYS: Final[dict[str, str]] = {
    "Requests": "RequestID",
    "Donations": "DonationID",
    "Reports": "ReportID",
    "Tasks": "TaskID",
    "Inventory": "ItemID",
    "CalendarLog": "EventDraftID",  # draft identity; CalendarEventID is for promotion
    "AuditLog": "AuditID",
}

# ── Affirmative consent values ────────────────────────────────────────────────

AFFIRMATIVE_VALUES: Final[set[str]] = {"yes", "true", "1", "approved"}

# ── Approved privacy levels for public export ────────────────────────────────

APPROVED_PRIVACY_LEVELS: Final[set[str]] = {
    "board-visible",
    "public-safe",
    "board-visible-test",
}

# ── Terminal statuses that should never be published ──────────────────────────

TERMINAL_STATUSES: Final[set[str]] = {
    "cancelled",
    "rejected",
    "draft",
    "needs-info",
    "private-review",
    "private-hold",
}

# ── Statuses that are allowed for public export (per type) ────────────────────

PUBLIC_STATUS_BY_TYPE: Final[dict[str, set[str]]] = {
    "Requests": {"ready", "open", "in-progress", "published"},
    "Donations": {"ready", "available", "received", "matched", "complete", "completed"},
    "Reports": {"ready", "complete", "completed", "published"},
    # Tasks and Inventory are never public
    "Tasks": set(),
    "Inventory": set(),
}

# ── Field names for common audit/approval columns ────────────────────────────

PUBLIC_SUMMARY_ALLOWED_FIELD: Final[str] = "PublicSummaryAllowed"
PUBLIC_LISTING_ALLOWED_FIELD: Final[str] = "PublicListingAllowed"
PRIVACY_LEVEL_FIELD: Final[str] = "PrivacyLevel"
LAST_UPDATED_FIELD: Final[str] = "LastUpdated"
CONSENT_TO_SHARE_FIELD: Final[str] = "ConsentToShare"
CONSENT_TO_PUBLIC_THANKS_FIELD: Final[str] = "ConsentToPublicThanks"

# ── Helper functions ──────────────────────────────────────────────────────────

def col(n: int) -> str:
    """Convert 1-indexed column number to A1 notation."""
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def get_header_range(tab: str) -> str:
    """Return A1 range string for the header row of a tab."""
    return f"{tab}!A1:{col(len(HEADERS[tab]))}1"


def get_full_range(tab: str) -> str:
    """Return A1 range string for the full used range of a tab (all rows, all columns)."""
    return f"{tab}!A:{col(len(HEADERS[tab]))}"


def get_primary_key(tab: str) -> str:
    """Return the primary key column name for a tab."""
    return PRIMARY_KEYS.get(tab, "")


def is_affirmative(value: str) -> bool:
    """Check if a string value represents affirmative consent."""
    return value.strip().lower() in AFFIRMATIVE_VALUES


def is_approved_privacy(value: str) -> bool:
    """Check if a privacy level is approved for public export."""
    return value.strip().lower() in APPROVED_PRIVACY_LEVELS


def is_public_status(tab: str, value: str) -> bool:
    """Check if a status value is allowed for public export for the given tab."""
    return value.strip().lower() in PUBLIC_STATUS_BY_TYPE.get(tab, set())


def is_terminal_status(value: str) -> bool:
    """Check if a status is terminal (never public)."""
    return value.strip().lower() in TERMINAL_STATUSES


# ── Schema validation ────────────────────────────────────────────────────────

def validate_schema_consistency() -> list[str]:
    """
    Validate that the schema has no duplicate headers within any tab.
    Returns list of error messages (empty if valid).
    """
    errors = []
    for tab, headers in HEADERS.items():
        seen = set()
        for i, h in enumerate(headers):
            if h in seen:
                errors.append(f"{tab}: duplicate header '{h}' at index {i}")
            seen.add(h)
    return errors


# Run validation on import
_VALIDATION_ERRORS = validate_schema_consistency()
if _VALIDATION_ERRORS:
    raise RuntimeError(f"Schema validation failed: {_VALIDATION_ERRORS}")

# ── Tab order for deterministic processing ────────────────────────────────────

TAB_ORDER: Final[list[str]] = [
    "Requests",
    "Donations",
    "Reports",
    "Tasks",
    "Inventory",
    "CalendarLog",
    "AuditLog",
]