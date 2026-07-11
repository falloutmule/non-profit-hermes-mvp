"""EVENT-002 durable event-draft backend — strict TDD, all Google access faked.

Covers the contract Tests 1-8:
  1. new draft creates exactly one CalendarLog row with correct defaults
  2. upsert of existing draft preserves row count and omitted values
  3. strict update of unknown EventDraftID returns not_found, no row creation
  4. approval-gate table blocks (missing title / start / naive start / invalid end /
     ApprovalStatus not approved / Status not ready) — no insert, CalendarEventID blank
  5. successful fake creation does exactly one insert into the SAME populated row
  6. duplicate retry returns already_created with no second insert
  7. privacy fields are stored separately and operational title uses private fields
  8. EVENT-001 header guard + 24-column schema preserved; module compiles

No network, no live Google calls. Sheets/Calendar are in-memory fakes.
"""
from __future__ import annotations

import importlib.util
import re
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_CALENDAR_HEADERS = [
    "CalendarEventID", "EventTitle", "EventType", "StartDateTime",
    "EndDateTime", "Location", "PrivateLocation", "Description",
    "Attendees", "RelatedTaskID", "RelatedRequestID", "RelatedDonationID",
    "Status", "CreatedBy", "LastUpdated", "EventDraftID", "PrivacyLevel",
    "PublicCalendarAllowed", "PublicTitle", "PublicDescription",
    "PublicLocation", "ApprovalStatus", "SourceMessageLink", "Notes",
]


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ops = load_module("event_ops", "scripts/non_profit_hermes_ops.py")


# ── In-memory fake Google Sheets (stateful, mirrors the 24-col CalendarLog) ──

class FakeSheetsValues:
    def __init__(self, store: "FakeSheetsStore"):
        self.store = store

    def get(self, **kwargs):
        return _Result(self.store._do_get(kwargs["range"]))

    def update(self, **kwargs):
        self.store._do_update(kwargs["range"], kwargs["body"])
        return self

    def append(self, **kwargs):
        self.store._do_append(kwargs["range"], kwargs["body"])
        return self

    def execute(self):
        return {}


class _Result:
    def __init__(self, payload: dict):
        self._payload = payload

    def execute(self):
        return self._payload


class FakeSheetsStore:
    """Minimal Sheets backend: keeps {tab: [header, row, ...]} in memory."""

    def __init__(self):
        self.tabs: dict[str, list[list[str]]] = {}
        self.values_resource = FakeSheetsValues(self)

    def spreadsheets(self):
        return self

    def values(self):
        return self.values_resource

    def _tab_of(self, rng: str) -> str:
        return rng.split("!")[0]

    def _row_of(self, rng: str) -> int:
        m = re.search(r"!A(\d+)", rng)
        return int(m.group(1)) if m else 1

    def _do_get(self, rng: str):
        tab = self._tab_of(rng)
        return {"values": self.tabs.get(tab, [])}

    def _do_update(self, rng: str, body):
        tab = self._tab_of(rng)
        row_idx = self._row_of(rng) - 1
        values = body["values"][0]
        rows = self.tabs.setdefault(tab, [])
        while len(rows) <= row_idx:
            rows.append([""] * len(values))
        rows[row_idx] = values
        return {"updatedRows": 1}

    def _do_append(self, rng: str, body):
        tab = self._tab_of(rng)
        values = body["values"][0]
        rows = self.tabs.setdefault(tab, [])
        rows.append(values)
        return {"updates": {"updatedRows": 1}}

    def calendar_log_rows(self) -> list[list[str]]:
        """Return data rows (excluding header) for CalendarLog."""
        rows = self.tabs.get("CalendarLog", [])
        return rows[1:] if rows else []

    def row_by_draft(self, draft_id: str) -> dict | None:
        header = EXPECTED_CALENDAR_HEADERS
        for raw in self.calendar_log_rows():
            rec = {header[i]: raw[i] if i < len(raw) else "" for i in range(len(header))}
            if rec.get("EventDraftID") == draft_id:
                return rec
        return None


# ── In-memory fake Google Calendar (counts inserts, captures body) ──

class FakeCalendarInsert:
    def __init__(self, counter: "FakeCalendarService"):
        self.counter = counter

    def insert(self, **kwargs):
        self.counter.insert_bodies.append(kwargs.get("body"))
        self.counter.insert_count += 1
        return self

    def execute(self):
        return {"id": f"cal-{self.counter.insert_count}"}


class FakeCalendarService:
    def __init__(self):
        self.insert_count = 0
        self.insert_bodies: list[dict] = []
        self._events = FakeCalendarInsert(self)

    def events(self):
        return self._events


# ── Test helpers ──

APPROVED_READY_BASE = dict(
    event_title="Board meeting",
    event_type="meeting",
    start_time="2026-07-12T09:00:00+00:00",
    end_time="2026-07-12T10:00:00+00:00",
    description="Internal board meeting",
    location="Back office",
    privacy_level="private-review",
    public_calendar_allowed="no",
    public_title="Community workshop",
    public_location="Public hall",
    public_description="Safe public description",
    approval_status="approved",
    status="ready",
)


class EventDraftBackendTests(unittest.TestCase):
    # ── Test 1: new draft ──
    def test_1_new_draft_creates_single_row_with_defaults(self):
        sheets = FakeSheetsStore()
        res = ops.upsert_event_draft(sheets, **APPROVED_READY_BASE)

        self.assertEqual(res["status"], "created")
        self.assertTrue(res["id"].startswith("EVT-"))
        self.assertEqual(len(sheets.calendar_log_rows()), 1)

        rec = sheets.row_by_draft(res["id"])
        self.assertIsNotNone(rec)
        self.assertEqual(rec["CalendarEventID"], "")
        self.assertEqual(rec["EventTitle"], "Board meeting")
        self.assertEqual(rec["PrivacyLevel"], "private-review")
        self.assertEqual(rec["PublicCalendarAllowed"], "no")
        self.assertEqual(rec["ApprovalStatus"], "approved")
        self.assertEqual(rec["Status"], "ready")
        self.assertEqual(rec["CreatedBy"], "Hermes")

    # ── Test 1b: generated id when absent ──
    def test_1b_generated_evt_id_when_absent(self):
        sheets = FakeSheetsStore()
        res = ops.upsert_event_draft(sheets, event_title="T")
        self.assertTrue(re.fullmatch(r"EVT-[0-9A-F]{8}", res["id"]))
        self.assertEqual(len(sheets.calendar_log_rows()), 1)

    # ── Test 1c: defaults applied when no status/approval/privacy provided ──
    def test_1c_new_draft_defaults_when_optional_omitted(self):
        sheets = FakeSheetsStore()
        res = ops.upsert_event_draft(sheets, event_title="Draft minimal",
                                     start_time="2026-07-13T08:00:00+00:00")
        rec = sheets.row_by_draft(res["id"])
        self.assertEqual(rec["PrivacyLevel"], "private-review")
        self.assertEqual(rec["PublicCalendarAllowed"], "no")
        self.assertEqual(rec["ApprovalStatus"], "needs-info")
        self.assertEqual(rec["Status"], "needs-info")
        self.assertEqual(rec["CreatedBy"], "Hermes")
        self.assertEqual(rec["CalendarEventID"], "")

    # ── Test 2: upsert existing preserves row count + omitted values ──
    def test_2_upsert_existing_preserves_row_count_and_omitted(self):
        sheets = FakeSheetsStore()
        created = ops.upsert_event_draft(sheets, **APPROVED_READY_BASE)
        did = created["id"]

        # Update only the title; start_time/status/etc omitted.
        upd = ops.upsert_event_draft(
            sheets, event_draft_id=did, event_title="Renamed board meeting",
        )
        self.assertEqual(upd["status"], "updated")
        # No second row created.
        self.assertEqual(len(sheets.calendar_log_rows()), 1)

        rec = sheets.row_by_draft(did)
        self.assertEqual(rec["EventTitle"], "Renamed board meeting")
        # Omitted values preserved from original.
        self.assertEqual(rec["StartDateTime"], APPROVED_READY_BASE["start_time"])
        self.assertEqual(rec["EndDateTime"], APPROVED_READY_BASE["end_time"])
        self.assertEqual(rec["Description"], APPROVED_READY_BASE["description"])
        self.assertEqual(rec["Location"], APPROVED_READY_BASE["location"])
        self.assertEqual(rec["ApprovalStatus"], "approved")
        self.assertEqual(rec["Status"], "ready")
        self.assertEqual(rec["CalendarEventID"], "")  # stays blank on normal update
        self.assertEqual(rec["PublicTitle"], APPROVED_READY_BASE["public_title"])
        self.assertEqual(rec["PublicDescription"], APPROVED_READY_BASE["public_description"])

    # ── Test 3: strict unknown update not_found ──
    def test_3_strict_unknown_update_returns_not_found_no_row(self):
        sheets = FakeSheetsStore()
        ops.upsert_event_draft(sheets, event_title="Real", start_time="2026-07-14T09:00:00+00:00")
        before = len(sheets.calendar_log_rows())

        res = ops.update_event_draft(sheets, event_draft_id="EVT-DOES-NOT-EXIST",
                                     event_title="Phantom")
        self.assertEqual(res["status"], "not_found")
        # No silent row creation.
        self.assertEqual(len(sheets.calendar_log_rows()), before)
        self.assertIsNone(sheets.row_by_draft("EVT-DOES-NOT-EXIST"))

    # ── Test 3b: strict update partial non-empty preserves CalendarEventID ──
    def test_3b_strict_update_preserves_calendar_event_id(self):
        sheets = FakeSheetsStore()
        created = ops.upsert_event_draft(sheets, **APPROVED_READY_BASE)
        did = created["id"]
        # Simulate an already-created draft by writing a CalendarEventID via direct set.
        rec = sheets.row_by_draft(did)
        idx = sheets.calendar_log_rows().index(
            [rec.get(h, "") for h in EXPECTED_CALENDAR_HEADERS]
        ) + 1  # +1 for header
        rows = sheets.tabs["CalendarLog"]
        cid_col = EXPECTED_CALENDAR_HEADERS.index("CalendarEventID")
        rows[idx][cid_col] = "cal-existing"

        res = ops.update_event_draft(sheets, event_draft_id=did, event_title="Edited")
        self.assertEqual(res["status"], "updated")
        self.assertEqual(sheets.row_by_draft(did)["CalendarEventID"], "cal-existing")

    # ── Test 4: approval-gate blocks ──
    def _make_draft(self, sheets: FakeSheetsStore, **overrides) -> str:
        kwargs = dict(APPROVED_READY_BASE)
        kwargs.update(overrides)
        return ops.upsert_event_draft(sheets, **kwargs)["id"]

    def _assert_blocked(self, did: str, sheets: FakeSheetsStore, calendar: FakeCalendarService):
        res = ops.create_calendar_event_from_draft(calendar, sheets, event_draft_id=did)
        self.assertIn(res["status"], ("blocked", "not_found"))
        self.assertEqual(calendar.insert_count, 0)  # no insert happened
        rec = sheets.row_by_draft(did)
        self.assertEqual(rec["CalendarEventID"], "")  # stays blank

    def test_4_approval_gate_blocks_all_invalid_cases(self):
        cases = {
            "missing_title": {"event_title": ""},
            "missing_start": {"start_time": ""},
            "naive_start": {"start_time": "2026-07-12T09:00:00"},
            "invalid_end_naive": {"end_time": "2026-07-12T10:00:00"},
            "approval_not_approved": {"approval_status": "needs-info"},
            "status_not_ready": {"status": "needs-info"},
        }
        for label, overrides in cases.items():
            with self.subTest(label=label):
                sheets = FakeSheetsStore()
                calendar = FakeCalendarService()
                did = self._make_draft(sheets, **overrides)
                self._assert_blocked(did, sheets, calendar)

    # ── Test 5: successful fake creation — one insert, same row populated ──
    def test_5_successful_creation_one_insert_same_row(self):
        sheets = FakeSheetsStore()
        calendar = FakeCalendarService()
        did = self._make_draft(sheets)

        res = ops.create_calendar_event_from_draft(calendar, sheets, event_draft_id=did)
        self.assertEqual(res["status"], "created")
        self.assertEqual(res["id"], did)
        self.assertTrue(res["calendar_id"].startswith("cal-"))

        # Exactly ONE insert, into the SAME single CalendarLog row.
        self.assertEqual(calendar.insert_count, 1)
        self.assertEqual(len(sheets.calendar_log_rows()), 1)

        rec = sheets.row_by_draft(did)
        self.assertEqual(rec["CalendarEventID"], res["calendar_id"])
        self.assertEqual(rec["ApprovalStatus"], "created")
        self.assertEqual(rec["Status"], "confirmed")

        # Operational calendar title uses PRIVATE fields, prefixed, never PublicTitle.
        body = calendar.insert_bodies[0]
        self.assertEqual(body["summary"], f"{did} — Board meeting")
        self.assertNotEqual(body["summary"], APPROVED_READY_BASE["public_title"])
        self.assertEqual(body["description"], "Internal board meeting")
        self.assertEqual(body["location"], "Back office")

    # ── Test 6: duplicate retry returns already_created, no second insert ──
    def test_6_duplicate_retry_already_created_no_second_insert(self):
        sheets = FakeSheetsStore()
        calendar = FakeCalendarService()
        did = self._make_draft(sheets)

        first = ops.create_calendar_event_from_draft(calendar, sheets, event_draft_id=did)
        self.assertEqual(first["status"], "created")
        self.assertEqual(calendar.insert_count, 1)

        retry = ops.create_calendar_event_from_draft(calendar, sheets, event_draft_id=did)
        self.assertEqual(retry["status"], "already_created")
        self.assertEqual(retry["calendar_id"], first["calendar_id"])
        # Still exactly one insert total + one CalendarLog row.
        self.assertEqual(calendar.insert_count, 1)
        self.assertEqual(len(sheets.calendar_log_rows()), 1)

    # ── Test 7: privacy fields stored separately ──
    def test_7_privacy_fields_preserved_separate(self):
        sheets = FakeSheetsStore()
        calendar = FakeCalendarService()
        did = ops.upsert_event_draft(
            sheets,
            event_title="Secret planning session",
            description="Private operational notes",
            location="Private venue",
            private_location="",
            public_title="Public community workshop",
            public_description="Safe public blurb",
            public_location="Public square",
            start_time="2026-07-15T09:00:00+00:00",
            approval_status="approved",
            status="ready",
        )["id"]

        rec = sheets.row_by_draft(did)
        # Private vs public stored in distinct columns.
        self.assertEqual(rec["EventTitle"], "Secret planning session")
        self.assertEqual(rec["PublicTitle"], "Public community workshop")
        self.assertNotEqual(rec["EventTitle"], rec["PublicTitle"])
        self.assertEqual(rec["Description"], "Private operational notes")
        self.assertEqual(rec["PublicDescription"], "Safe public blurb")
        self.assertEqual(rec["Location"], "Private venue")
        self.assertEqual(rec["PublicLocation"], "Public square")

        res = ops.create_calendar_event_from_draft(calendar, sheets, event_draft_id=did)
        self.assertEqual(res["status"], "created")
        body = calendar.insert_bodies[0]
        # Operational title + description come from PRIVATE fields.
        self.assertEqual(body["summary"], f"{did} — Secret planning session")
        self.assertEqual(body["description"], "Private operational notes")
        self.assertNotEqual(body["summary"], "Public community workshop")

    # ── Test 7b: private_location hides calendar location ──
    def test_7b_private_location_hides_calendar_location(self):
        sheets = FakeSheetsStore()
        calendar = FakeCalendarService()
        did = ops.upsert_event_draft(
            sheets,
            event_title="Sensitive meet",
            location="Should not leak",
            private_location="Hidden address",
            start_time="2026-07-16T09:00:00+00:00",
            approval_status="approved",
            status="ready",
        )["id"]
        ops.create_calendar_event_from_draft(calendar, sheets, event_draft_id=did)
        body = calendar.insert_bodies[0]
        self.assertNotIn("location", body)  # private -> no public location field

    # ── Test 8: EVENT-001 header guard + 24-column schema preserved ──
    def test_8_calendarlog_schema_unchanged_24_columns(self):
        self.assertEqual(ops.HEADERS["CalendarLog"], EXPECTED_CALENDAR_HEADERS)
        self.assertEqual(len(ops.HEADERS["CalendarLog"]), 24)

    def test_8b_event001_header_guard_before_append_still_holds(self):
        sheets = FakeSheetsStore()
        calendar = FakeCalendarService()
        ops.create_calendar_event(
            calendar, sheets,
            event_title="Safe local test event",
            start_time=datetime(2026, 7, 11, 9, tzinfo=timezone.utc),
            end_time=datetime(2026, 7, 11, 10, tzinfo=timezone.utc),
        )
        # Inspect the raw operations by re-running against a recording fake.
        rec = RecordingSheets()
        ops.create_calendar_event(
            RecordingCalendar(), rec,
            event_title="Safe local test event 2",
            start_time=datetime(2026, 7, 11, 9, tzinfo=timezone.utc),
            end_time=datetime(2026, 7, 11, 10, tzinfo=timezone.utc),
        )
        header_idx = next(
            i for i, c in enumerate(rec.calls)
            if c[0] == "update" and c[1]["range"].startswith("CalendarLog!A1")
        )
        append_idx = next(
            i for i, c in enumerate(rec.calls)
            if c[0] == "append" and c[1]["range"].startswith("CalendarLog!")
        )
        self.assertLess(header_idx, append_idx)


class RecordingSheets:
    def __init__(self):
        self.calls = []
        self.tabs = {}

    def spreadsheets(self):
        return self

    def values(self):
        return self

    def get(self, **kwargs):
        self.calls.append(("get", kwargs))
        tab = kwargs["range"].split("!")[0]
        return _Result({"values": self.tabs.get(tab, [])})

    def update(self, **kwargs):
        self.calls.append(("update", kwargs))
        return _Result({})

    def append(self, **kwargs):
        self.calls.append(("append", kwargs))
        return _Result({})


class RecordingCalendar:
    def events(self):
        return self

    def insert(self, **kwargs):
        return self

    def execute(self):
        return {"id": "rec-cal-1"}


if __name__ == "__main__":
    unittest.main()
