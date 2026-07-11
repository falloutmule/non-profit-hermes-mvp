"""Focused EVENT-001 privacy-gate tests; all Calendar access is fake/local."""
from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_SENTINEL = "PRIVATE-EVENT-LEAK-TEST-7F21"
EXPECTED_CALENDAR_HEADERS = [
    "CalendarEventID", "EventTitle", "EventType", "StartDateTime",
    "EndDateTime", "Location", "PrivateLocation", "Description",
    "Attendees", "RelatedTaskID", "RelatedRequestID", "RelatedDonationID",
    "Status", "CreatedBy", "LastUpdated", "EventDraftID", "PrivacyLevel",
    "PublicCalendarAllowed", "PublicTitle", "PublicDescription",
    "PublicLocation", "ApprovalStatus", "SourceMessageLink", "Notes",
]
PUBLIC_EXPORT_HEADERS = [
    "CalendarEventID", "EventTitle", "EventType", "StartDateTime",
    "EndDateTime", "Description", "Location", "Status",
]


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ops = load_module("event_ops", "scripts/non_profit_hermes_ops.py")
sync = load_module("event_sync", "scripts/sync_approved_safe_data.py")
router = load_module("event_router", "scripts/telegram_intake_router.py")


class FakeEventsResource:
    def __init__(self, items):
        self.items = items
        self.list_calls = []

    def list(self, **kwargs):
        self.list_calls.append(kwargs)
        return self

    def execute(self):
        return {"items": self.items}


class FakeCalendarService:
    def __init__(self, items):
        self.events_resource = FakeEventsResource(items)

    def events(self):
        return self.events_resource


class FakePagedEventsResource:
    def __init__(self, pages):
        self.pages = pages
        self.list_calls = []
        self.page_token = None

    def list(self, **kwargs):
        self.list_calls.append(kwargs)
        self.page_token = kwargs.get("pageToken")
        return self

    def execute(self):
        return self.pages[self.page_token]


class FakePagedCalendarService:
    def __init__(self, pages):
        self.events_resource = FakePagedEventsResource(pages)

    def events(self):
        return self.events_resource


class FakeCalendarCreateEvents:
    def __init__(self):
        self.insert_body = None

    def insert(self, **kwargs):
        self.insert_body = kwargs["body"]
        return self

    def execute(self):
        return {"id": "evt-created"}


class FakeCalendarCreateService:
    def __init__(self):
        self.events_resource = FakeCalendarCreateEvents()

    def events(self):
        return self.events_resource


class FakeSheetsValues:
    def __init__(self):
        self.operations = []

    def update(self, **kwargs):
        self.operations.append(("update", kwargs))
        return self

    def append(self, **kwargs):
        self.operations.append(("append", kwargs))
        return self

    def execute(self):
        return {}


class FakeSheetsService:
    def __init__(self):
        self.values_resource = FakeSheetsValues()

    def spreadsheets(self):
        return self

    def values(self):
        return self.values_resource


def calendar_row(**overrides):
    values = {
        "CalendarEventID": "evt-public",
        "EventTitle": PRIVATE_SENTINEL,
        "EventType": "private-type",
        "StartDateTime": "2026-07-11T09:00:00+00:00",
        "EndDateTime": "2026-07-11T10:00:00+00:00",
        "Location": PRIVATE_SENTINEL,
        "PrivateLocation": PRIVATE_SENTINEL,
        "Description": PRIVATE_SENTINEL,
        "Attendees": "private@example.invalid",
        "RelatedTaskID": "TASK-PRIVATE",
        "RelatedRequestID": "REQ-PRIVATE",
        "RelatedDonationID": "DON-PRIVATE",
        "Status": "confirmed",
        "CreatedBy": "Hermes",
        "LastUpdated": "2026-07-10T00:00:00+00:00",
        "EventDraftID": "DRAFT-001",
        "PrivacyLevel": "public-safe",
        "PublicCalendarAllowed": "yes",
        "PublicTitle": "Community pantry test",
        "PublicDescription": "Approved-safe event description",
        "PublicLocation": "Public service area",
        "ApprovalStatus": "approved",
        "SourceMessageLink": "https://private.invalid/message",
        "Notes": PRIVATE_SENTINEL,
    }
    values.update(overrides)
    return [values.get(header, "") for header in EXPECTED_CALENDAR_HEADERS]


class EventCalendarPrivacyGateTests(unittest.TestCase):
    def test_calendarlog_headers_are_appended_and_sync_schema_matches_backend(self):
        self.assertEqual(ops.HEADERS["CalendarLog"], EXPECTED_CALENDAR_HEADERS)
        self.assertEqual(sync.HEADERS["CalendarLog"], EXPECTED_CALENDAR_HEADERS)

    def test_private_row_is_excluded_even_when_raw_fields_contain_sentinel(self):
        rows = [EXPECTED_CALENDAR_HEADERS, calendar_row(PrivacyLevel="private-review")]
        calendar = FakeCalendarService([{"id": "evt-public", "status": "confirmed"}])

        exported = sync.safe_calendar_export(rows, calendar)

        self.assertEqual(exported, [])
        self.assertNotIn(PRIVATE_SENTINEL, repr(exported))

    def test_approved_public_row_exports_only_safe_fields_after_exact_calendar_join(self):
        rows = [EXPECTED_CALENDAR_HEADERS, calendar_row()]
        calendar = FakeCalendarService([
            {"id": "evt-public", "status": "confirmed", "summary": PRIVATE_SENTINEL},
            {"id": "evt-unrelated", "status": "confirmed", "summary": PRIVATE_SENTINEL},
        ])

        exported = sync.safe_calendar_export(rows, calendar)

        self.assertEqual(exported, [{
            "CalendarEventID": "evt-public",
            "EventTitle": "Community pantry test",
            "EventType": "private-type",
            "StartDateTime": "2026-07-11T09:00:00+00:00",
            "EndDateTime": "2026-07-11T10:00:00+00:00",
            "Description": "Approved-safe event description",
            "Location": "Public service area",
            "Status": "confirmed",
        }])
        self.assertEqual(list(exported[0]), PUBLIC_EXPORT_HEADERS)
        self.assertNotIn(PRIVATE_SENTINEL, repr(exported))
        self.assertEqual(len(calendar.events_resource.list_calls), 1)

    def test_approved_row_with_live_id_only_on_second_page_exports(self):
        rows = [EXPECTED_CALENDAR_HEADERS, calendar_row(CalendarEventID="evt-page-two")]
        calendar = FakePagedCalendarService({
            None: {"items": [{"id": "evt-other", "status": "confirmed"}], "nextPageToken": "page-2"},
            "page-2": {"items": [{"id": "evt-page-two", "status": "confirmed"}]},
        })

        exported = sync.safe_calendar_export(rows, calendar)

        self.assertEqual(exported[0]["CalendarEventID"], "evt-page-two")
        self.assertEqual([call.get("pageToken") for call in calendar.events_resource.list_calls], [None, "page-2"])

    def test_stale_and_cancelled_calendar_ids_are_not_exported(self):
        rows = [
            EXPECTED_CALENDAR_HEADERS,
            calendar_row(CalendarEventID="evt-missing"),
            calendar_row(CalendarEventID="evt-cancelled", PublicTitle="Cancelled safe title"),
        ]
        calendar = FakeCalendarService([
            {"id": "evt-cancelled", "status": "cancelled"},
        ])

        exported = sync.safe_calendar_export(rows, calendar)

        self.assertEqual(exported, [])

    def test_calendarlog_header_update_precedes_calendarlog_append(self):
        calendar = FakeCalendarCreateService()
        sheets = FakeSheetsService()
        with patch.object(ops, "_calendar_event_exists", return_value=None):
            ops.create_calendar_event(
                calendar, sheets, event_title="Safe local test event",
                start_time=datetime(2026, 7, 11, 9, tzinfo=timezone.utc),
                end_time=datetime(2026, 7, 11, 10, tzinfo=timezone.utc),
            )

        operations = sheets.values_resource.operations
        header_update = next(
            index for index, (kind, call) in enumerate(operations)
            if kind == "update" and call["range"].startswith("CalendarLog!")
        )
        calendar_append = next(
            index for index, (kind, call) in enumerate(operations)
            if kind == "append" and call["range"].startswith("CalendarLog!")
        )
        self.assertLess(header_update, calendar_append)

    def test_calendar_export_denies_invalid_required_values_even_when_live(self):
        deny_cases = (
            ("empty CalendarEventID", {"CalendarEventID": ""}),
            ("invalid PublicCalendarAllowed", {"PublicCalendarAllowed": "no"}),
            ("invalid ApprovalStatus", {"ApprovalStatus": "pending"}),
            ("invalid Status", {"Status": "draft"}),
            ("empty PublicTitle", {"PublicTitle": ""}),
        )
        calendar = FakeCalendarService([{"id": "evt-public", "status": "confirmed"}])

        for label, overrides in deny_cases:
            with self.subTest(label=label):
                self.assertEqual(sync.safe_calendar_export([EXPECTED_CALENDAR_HEADERS, calendar_row(**overrides)], calendar), [])

    def test_daily_summary_accepts_eight_field_calendar_export_and_deduplicates_titles(self):
        event = {
            "CalendarEventID": "evt-daily-1",
            "EventTitle": "Community pantry test",
            "EventType": "test",
            "StartDateTime": "2026-07-10T09:00:00+00:00",
            "EndDateTime": "2026-07-10T10:00:00+00:00",
            "Description": "Approved-safe event description",
            "Location": "Public service area",
            "Status": "confirmed",
        }
        exports = {
            "approved_needs.json": [],
            "approved_donations.json": [],
            "approved_reports.json": [],
            "approved_calendar.json": [event, {**event, "CalendarEventID": "evt-daily-2"}],
            "approved_board_log.json": [],
        }
        with (
            patch.object(router, "run_sync", return_value={"marker": "EVENT-001-MARKER", "rows": {"approved_calendar": 2}}),
            patch.object(router, "read_json", side_effect=lambda name: exports[name]),
            patch.object(router, "now_utc", return_value=datetime(2026, 7, 10, tzinfo=timezone.utc)),
        ):
            summary = router.run_daily_summary()

        self.assertEqual(summary.count("Community pantry test (confirmed)"), 1)
        self.assertIn("Marker: EVENT-001-MARKER", summary)
        self.assertIn("daily_plugin_version: website-links-dedup-003", summary)


if __name__ == "__main__":
    unittest.main()
