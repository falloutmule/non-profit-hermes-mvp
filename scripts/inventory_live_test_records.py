"""Pure, read-only classification for offline inventory of test and live records."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
from typing import Any

ABANDONED_DRAFT_REVIEW = "ABANDONED_DRAFT_REVIEW"
EVIDENCE_RETAIN = "EVIDENCE_RETAIN"
HISTORICAL_RETAIN = "HISTORICAL_RETAIN"
POSSIBLE_DUPLICATE_REVIEW = "POSSIBLE_DUPLICATE_REVIEW"
REAL_OPERATIONAL_DO_NOT_TOUCH = "REAL_OPERATIONAL_DO_NOT_TOUCH"
SAFE_FAKE_ACTIVE = "SAFE_FAKE_ACTIVE"
UNKNOWN_MANUAL_REVIEW = "UNKNOWN_MANUAL_REVIEW"
_SAFE_REFERENCE = re.compile(r"^[A-Z]{2,12}-[A-Z0-9-]{1,64}$", re.IGNORECASE)


def _text(record: Mapping[str, Any], field: str) -> str:
    value = record.get(field, "")
    return value.strip() if isinstance(value, str) else ""


def _record_ref(record: Mapping[str, Any], index: int) -> str:
    for field in ("EventDraftID", "RecordID", "AuditID", "RequestID", "DonationID", "ReportID"):
        value = _text(record, field)
        if _SAFE_REFERENCE.fullmatch(value):
            return value
    return f"record-{index + 1}"


def _result(record: Mapping[str, Any], index: int, classification: str, confidence: str, reason: str) -> dict[str, str]:
    return {
        "record_ref": _record_ref(record, index),
        "classification": classification,
        "confidence": confidence,
        "reason": reason,
    }


def _is_event_003_abandoned_draft(record: Mapping[str, Any]) -> bool:
    combined = " ".join(_text(record, field).lower() for field in ("EventTitle", "EventType", "Notes"))
    return (
        "event-003" in combined
        and "safe fake" in combined
        and _text(record, "Status").lower() == "cancelled"
        and _text(record, "ApprovalStatus").lower() == "rejected"
        and not _text(record, "CalendarEventID")
    )


def _is_event_004_evidence(record: Mapping[str, Any]) -> bool:
    combined = " ".join(_text(record, field).lower() for field in (
        "EventTitle", "EventType", "Description", "Notes",
    ))
    return (
        "event-004" in combined
        and "safe fake" in combined
        and "synthetic" in combined
        and _text(record, "Status").lower() == "confirmed"
        and _text(record, "ApprovalStatus").lower() == "created"
        and bool(_text(record, "CalendarEventID"))
    )


def _is_explicit_active_fake(record: Mapping[str, Any]) -> bool:
    combined = " ".join(_text(record, field).lower() for field in (
        "EventTitle", "NeedDescription", "ItemDescription", "Summary", "Description", "Notes",
    ))
    return _text(record, "TestLifecycle").lower() == "active" and "safe fake" in combined


def _is_explicit_historical_record(record: Mapping[str, Any]) -> bool:
    return (
        _text(record, "RetentionDisposition").lower() == "historical-retain"
        and _text(record, "Status").lower() in {"completed", "confirmed", "cancelled"}
    )


def _has_personal_operational_data(record: Mapping[str, Any]) -> bool:
    return any(_text(record, field) for field in (
        "ContactName", "ContactEmail", "Phone", "Attendees", "PrivateLocation",
    ))


def _is_duplicate_review_candidate(record: Mapping[str, Any]) -> bool:
    """Require an explicit fixture field before duplicate-only classification."""
    return record.get("DuplicateReviewCandidate") is True


def _stable_identity(record: Mapping[str, Any]) -> str:
    for field in ("EventDraftID", "RecordID", "AuditID", "RequestID", "DonationID", "ReportID"):
        value = _text(record, field)
        if _SAFE_REFERENCE.fullmatch(value):
            return f"{field}:{value.casefold()}"
    return ""


def classify_records(records: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    """Classify caller-owned records without mutating them or performing I/O."""
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes, bytearray)):
        return [{
            "record_ref": "record-1",
            "classification": UNKNOWN_MANUAL_REVIEW,
            "confidence": "low",
            "reason": "Records input is incomplete; requires manual review.",
        }]

    identities: dict[str, int] = {}
    for record in records:
        if isinstance(record, Mapping):
            identity = _stable_identity(record)
            if identity:
                identities[identity] = identities.get(identity, 0) + 1

    results: list[dict[str, str]] = []
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            results.append({
                "record_ref": f"record-{index + 1}",
                "classification": UNKNOWN_MANUAL_REVIEW,
                "confidence": "low",
                "reason": "Record is not a field mapping and requires manual review.",
            })
        elif _has_personal_operational_data(record):
            results.append(_result(
                record,
                index,
                REAL_OPERATIONAL_DO_NOT_TOUCH,
                "high",
                "Personal operational data is present; do not alter this record.",
            ))
        elif _is_event_004_evidence(record):
            results.append(_result(
                record,
                index,
                EVIDENCE_RETAIN,
                "high",
                "Complete EVENT-004 synthetic verification evidence must be retained.",
            ))
        elif _is_event_003_abandoned_draft(record):
            results.append(_result(
                record,
                index,
                ABANDONED_DRAFT_REVIEW,
                "high",
                "Explicit EVENT-003 synthetic draft is cancelled and rejected; retain for human review.",
            ))
        elif _is_explicit_active_fake(record):
            results.append(_result(
                record,
                index,
                SAFE_FAKE_ACTIVE,
                "high",
                "Explicit active synthetic fixture must remain available for test coverage.",
            ))
        elif _is_explicit_historical_record(record):
            results.append(_result(
                record,
                index,
                HISTORICAL_RETAIN,
                "high",
                "Explicit historical retention marker requires preservation.",
            ))
        elif (
            _is_duplicate_review_candidate(record)
            and identities.get(_stable_identity(record), 0) > 1
        ):
            results.append(_result(
                record,
                index,
                POSSIBLE_DUPLICATE_REVIEW,
                "high",
                "Repeated stable identity requires review; no action is inferred.",
            ))
        else:
            results.append(_result(
                record,
                index,
                UNKNOWN_MANUAL_REVIEW,
                "low",
                "Evidence is incomplete; requires manual review.",
            ))
    return results
