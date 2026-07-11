"""
CLEANUP-002 Schema Parity Tests

Verifies that backend (non_profit_hermes_ops.py) and sync (sync_approved_safe_data.py)
both import and use the exact same HEADERS from non_profit_hermes_schema.py.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative_path: str):
    import sys
    scripts_path = str(ROOT / "scripts")
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_schema_is_single_source() -> None:
    """Both modules must import HEADERS from the canonical schema module."""
    ops = load_module("ops_check", "scripts/non_profit_hermes_ops.py")
    sync = load_module("sync_check", "scripts/sync_approved_safe_data.py")
    schema = load_module("schema_check", "scripts/non_profit_hermes_schema.py")

    # They must have the SAME CONTENT (imported from schema module)
    assert ops.HEADERS == schema.HEADERS, "ops.HEADERS must equal schema.HEADERS"
    assert sync.HEADERS == schema.HEADERS, "sync.HEADERS must equal schema.HEADERS"


def test_no_duplicate_header_literals() -> None:
    """No HEADERS dict literal should exist in ops or sync modules."""
    ops_path = ROOT / "scripts/non_profit_hermes_ops.py"
    sync_path = ROOT / "scripts/sync_approved_safe_data.py"

    for path, label in [(ops_path, "ops"), (sync_path, "sync")]:
        content = path.read_text(encoding="utf-8")
        # Allow the import line, but no dict literal assignment to HEADERS
        assert "HEADERS = {" not in content, f"{label} module contains HEADERS dict literal — must import from schema"


def test_all_tabs_present() -> None:
    """All expected tabs must be defined in the schema."""
    schema = load_module("schema_check", "scripts/non_profit_hermes_schema.py")
    expected_tabs = {
        "Requests",
        "Donations",
        "Reports",
        "Tasks",
        "Inventory",
        "CalendarLog",
        "AuditLog",
    }
    assert set(schema.HEADERS.keys()) == expected_tabs


OBSERVED_LIVE_REPORTS_HEADERS = [
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
]


def test_reports_headers_match_observed_live_order_with_final_append() -> None:
    """Reports preserves the live order and appends only PublicSummaryAllowed."""
    schema = load_module("schema_check", "scripts/non_profit_hermes_schema.py")
    reports_headers = schema.HEADERS["Reports"]
    expected_headers = OBSERVED_LIVE_REPORTS_HEADERS + ["PublicSummaryAllowed"]

    assert reports_headers == expected_headers


def test_reports_header_update_is_append_only_relative_to_observed_live_header() -> None:
    """A header-only update cannot reorder or overwrite existing Reports fields."""
    schema = load_module("schema_check", "scripts/non_profit_hermes_schema.py")
    reports_headers = schema.HEADERS["Reports"]

    assert reports_headers[:len(OBSERVED_LIVE_REPORTS_HEADERS)] == OBSERVED_LIVE_REPORTS_HEADERS
    assert reports_headers[len(OBSERVED_LIVE_REPORTS_HEADERS):] == ["PublicSummaryAllowed"]
    assert reports_headers[-1] == "PublicSummaryAllowed"


def test_donations_has_new_fields() -> None:
    """Donations tab must include PrivacyLevel, PublicListingAllowed, LastUpdated."""
    schema = load_module("schema_check", "scripts/non_profit_hermes_schema.py")
    don_headers = schema.HEADERS["Donations"]
    assert "PrivacyLevel" in don_headers, "Donations missing PrivacyLevel"
    assert "PublicListingAllowed" in don_headers, "Donations missing PublicListingAllowed"
    assert "LastUpdated" in don_headers, "Donations missing LastUpdated"
    # Order: new columns appended at end
    assert don_headers[-3] == "PrivacyLevel"
    assert don_headers[-2] == "PublicListingAllowed"
    assert don_headers[-1] == "LastUpdated"


def test_primary_keys_defined() -> None:
    """Every tab must have a primary key defined."""
    schema = load_module("schema_check", "scripts/non_profit_hermes_schema.py")
    for tab in schema.HEADERS:
        if tab != "AuditLog":  # AuditLog handled specially
            assert tab in schema.PRIMARY_KEYS, f"{tab} missing PRIMARY_KEYS entry"


def test_calendar_log_schema_unchanged_24_cols() -> None:
    """CalendarLog must remain exactly 24 columns with the expected order."""
    schema = load_module("schema_check", "scripts/non_profit_hermes_schema.py")
    cal_headers = schema.HEADERS["CalendarLog"]
    assert len(cal_headers) == 24, f"CalendarLog must have 24 columns, got {len(cal_headers)}"
    expected = [
        "CalendarEventID", "EventTitle", "EventType", "StartDateTime",
        "EndDateTime", "Location", "PrivateLocation", "Description",
        "Attendees", "RelatedTaskID", "RelatedRequestID", "RelatedDonationID",
        "Status", "CreatedBy", "LastUpdated", "EventDraftID", "PrivacyLevel",
        "PublicCalendarAllowed", "PublicTitle", "PublicDescription",
        "PublicLocation", "ApprovalStatus", "SourceMessageLink", "Notes",
    ]
    assert cal_headers == expected, f"CalendarLog header order changed: {cal_headers}"


def test_no_duplicate_headers_in_any_tab() -> None:
    """Each tab's header list must have unique column names."""
    schema = load_module("schema_check", "scripts/non_profit_hermes_schema.py")
    for tab, headers in schema.HEADERS.items():
        seen = set()
        for h in headers:
            assert h not in seen, f"Duplicate header '{h}' in {tab}"
            seen.add(h)


if __name__ == "__main__":
    import sys
    import unittest

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)