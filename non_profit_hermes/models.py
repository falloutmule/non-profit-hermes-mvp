"""Canonical pure data models for Non-Profit Hermes Sheets and publication rules."""

from __future__ import annotations

from typing import Final


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

PRIMARY_KEYS: Final[dict[str, str]] = {
    "Requests": "RequestID",
    "Donations": "DonationID",
    "Reports": "ReportID",
    "Tasks": "TaskID",
    "Inventory": "ItemID",
    "CalendarLog": "EventDraftID",
    "AuditLog": "AuditID",
}

AFFIRMATIVE_VALUES: Final[set[str]] = {"yes", "true", "1", "approved"}

APPROVED_PRIVACY_LEVELS: Final[set[str]] = {
    "board-visible",
    "public-safe",
    "board-visible-test",
}

TERMINAL_STATUSES: Final[set[str]] = {
    "cancelled",
    "rejected",
    "draft",
    "needs-info",
    "private-review",
    "private-hold",
}

PUBLIC_STATUS_BY_TYPE: Final[dict[str, set[str]]] = {
    "Requests": {"ready", "open", "in-progress", "published"},
    "Donations": {"ready", "available", "received", "matched", "complete", "completed"},
    "Reports": {"ready", "complete", "completed", "published"},
    "Tasks": set(),
    "Inventory": set(),
}

PUBLIC_SUMMARY_ALLOWED_FIELD: Final[str] = "PublicSummaryAllowed"
PUBLIC_LISTING_ALLOWED_FIELD: Final[str] = "PublicListingAllowed"
PRIVACY_LEVEL_FIELD: Final[str] = "PrivacyLevel"
LAST_UPDATED_FIELD: Final[str] = "LastUpdated"
CONSENT_TO_SHARE_FIELD: Final[str] = "ConsentToShare"
CONSENT_TO_PUBLIC_THANKS_FIELD: Final[str] = "ConsentToPublicThanks"


def col(n: int) -> str:
    """Convert a 1-indexed column number to A1 notation."""

    value = ""
    while n:
        n, remainder = divmod(n - 1, 26)
        value = chr(65 + remainder) + value
    return value


def get_header_range(tab: str) -> str:
    """Return the A1 range for a tab's header row."""

    return f"{tab}!A1:{col(len(HEADERS[tab]))}1"


def get_full_range(tab: str) -> str:
    """Return the A1 range for all modeled columns of a tab."""

    return f"{tab}!A:{col(len(HEADERS[tab]))}"


def get_primary_key(tab: str) -> str:
    """Return the primary key column name for a tab, or an empty string."""

    return PRIMARY_KEYS.get(tab, "")


def is_affirmative(value: str) -> bool:
    """Return whether a value represents affirmative consent."""

    return value.strip().lower() in AFFIRMATIVE_VALUES


def is_approved_privacy(value: str) -> bool:
    """Return whether a privacy level may be exported publicly."""

    return value.strip().lower() in APPROVED_PRIVACY_LEVELS


def is_public_status(tab: str, value: str) -> bool:
    """Return whether a tab permits the supplied status for public export."""

    return value.strip().lower() in PUBLIC_STATUS_BY_TYPE.get(tab, set())


def is_terminal_status(value: str) -> bool:
    """Return whether a status must never be published."""

    return value.strip().lower() in TERMINAL_STATUSES


def validate_schema_consistency() -> list[str]:
    """Return duplicate-header errors for the canonical tab schemas."""

    errors: list[str] = []
    for tab, headers in HEADERS.items():
        seen: set[str] = set()
        for index, header in enumerate(headers):
            if header in seen:
                errors.append(f"{tab}: duplicate header '{header}' at index {index}")
            seen.add(header)
    return errors


_VALIDATION_ERRORS = validate_schema_consistency()
if _VALIDATION_ERRORS:
    raise RuntimeError(f"Schema validation failed: {_VALIDATION_ERRORS}")


TAB_ORDER: Final[list[str]] = [
    "Requests",
    "Donations",
    "Reports",
    "Tasks",
    "Inventory",
    "CalendarLog",
    "AuditLog",
]
