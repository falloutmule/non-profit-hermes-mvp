"""EVENT-004 offline proof: exact local authorization is the only promotion path."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


tir = load("event004_router", "scripts/telegram_intake_router.py")
ops = load("event004_ops", "scripts/non_profit_hermes_ops.py")
sync = load("event004_sync", "scripts/sync_approved_safe_data.py")
SRC = "telegram:6080816249"
OTHER_SRC = "telegram:9999999999"


class Result:
    def __init__(self, payload): self.payload = payload
    def execute(self): return self.payload


class FakeSheets:
    def __init__(self): self.tabs = {}; self.writes = []
    def spreadsheets(self): return self
    def values(self): return self
    def get(self, **kwargs): return Result({"values": self.tabs.get(kwargs["range"].split("!", 1)[0], [])})
    def update(self, **kwargs):
        tab, cell = kwargs["range"].split("!", 1); row = int(cell.split("A", 1)[1].split(":", 1)[0]) - 1
        rows = self.tabs.setdefault(tab, [])
        value = kwargs["body"]["values"][0]
        while len(rows) <= row: rows.append([""] * len(value))
        rows[row] = value; self.writes.append(("update", kwargs)); return self
    def append(self, **kwargs):
        tab = kwargs["range"].split("!", 1)[0]
        self.tabs.setdefault(tab, []).append(kwargs["body"]["values"][0]); self.writes.append(("append", kwargs)); return self
    def execute(self): return {}
    def row(self, draft_id):
        header = ops.HEADERS["CalendarLog"]
        for raw in self.tabs.get("CalendarLog", [])[1:]:
            record = {name: raw[i] if i < len(raw) else "" for i, name in enumerate(header)}
            if record["EventDraftID"] == draft_id: return record
        return None
    def rows(self): return self.tabs.get("CalendarLog", [])[1:]


class FakeCalendar:
    def __init__(self): self.insert_count = 0
    def events(self): return self
    def insert(self, **kwargs): self.insert_count += 1; return self
    def execute(self): return {"id": f"cal-{self.insert_count}"}


def create_ready_draft(sheets, calendar, *, title="Authorized event", source=SRC, **fields):
    data = {"event_title": title, "start": "2026-07-12T09:00:00-06:00", "end": "2026-07-12T10:00:00-06:00", "approval_status": "approved", "status": "ready"}
    data.update(fields)
    return tir.route_event(sheets, calendar, data, "", source, "private-review")


class Event004AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.auth_path = Path(self.temp.name) / "event_calendar_promotion_authorization.json"
        self.active_path = Path(self.temp.name) / "active.json"
        self.original_active = tir.ACTIVE_NEED_STATE_PATH
        tir.ACTIVE_NEED_STATE_PATH = self.active_path
    def tearDown(self):
        tir.ACTIVE_NEED_STATE_PATH = self.original_active
        self.temp.cleanup()
    def authorize(self, draft_id, source=SRC, expires=None):
        return tir.write_event_calendar_promotion_authorization(
            authorized_event_draft_id=draft_id, authorized_source_scope=source,
            expires_at=expires or (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
            authorization_path=self.auth_path,
        )
    def promote(self, sheets, calendar, draft_id, source=SRC, text=None, mode=tir.ONE_SHOT_CALENDAR_PROMOTION_MODE):
        return tir.route_event_followup(
            sheets, calendar, text or f"create_calendar=yes id={draft_id}", source,
            calendar_promotion_mode=mode, authorization_path=self.auth_path,
        )

    def test_disabled_by_default_and_confirmation_required(self):
        sheets, calendar = FakeSheets(), FakeCalendar(); draft = create_ready_draft(sheets, calendar)
        self.authorize(draft.record_id)
        disabled = self.promote(sheets, calendar, draft.record_id, mode=False)
        self.assertEqual(disabled.status, "needs-info"); self.assertEqual(calendar.insert_count, 0)
        required = self.promote(sheets, calendar, draft.record_id, text=f"id={draft.record_id}")
        self.assertEqual(required.status, "ready"); self.assertTrue(self.auth_path.exists()); self.assertEqual(calendar.insert_count, 0)

    def test_authorization_requires_exact_draft_source_and_unexpired_state(self):
        sheets, calendar = FakeSheets(), FakeCalendar(); first = create_ready_draft(sheets, calendar); second = create_ready_draft(sheets, calendar, title="Second")
        self.authorize(first.record_id)
        mismatch = self.promote(sheets, calendar, second.record_id)
        self.assertEqual(mismatch.status, "blocked"); self.assertEqual(calendar.insert_count, 0); self.assertTrue(self.auth_path.exists())
        self.authorize(first.record_id, OTHER_SRC)
        source_mismatch = self.promote(sheets, calendar, first.record_id)
        self.assertEqual(source_mismatch.status, "blocked"); self.assertEqual(calendar.insert_count, 0)
        self.authorize(first.record_id, expires=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat())
        expired = self.promote(sheets, calendar, first.record_id)
        self.assertEqual(expired.status, "blocked"); self.assertEqual(calendar.insert_count, 0)

    def test_one_use_success_same_row_and_idempotent_retry_without_authorization(self):
        sheets, calendar = FakeSheets(), FakeCalendar(); draft = create_ready_draft(sheets, calendar)
        self.authorize(draft.record_id)
        promoted = self.promote(sheets, calendar, draft.record_id)
        self.assertEqual(promoted.status, "confirmed"); self.assertEqual(calendar.insert_count, 1); self.assertFalse(self.auth_path.exists())
        self.assertEqual(len(sheets.rows()), 1); self.assertEqual(sheets.row(draft.record_id)["CalendarEventID"], promoted.calendar_event_id)
        retry = self.promote(sheets, calendar, draft.record_id)
        self.assertEqual(retry.backend_status, "already_created"); self.assertEqual(retry.calendar_event_id, promoted.calendar_event_id); self.assertEqual(calendar.insert_count, 1)
        another = create_ready_draft(sheets, calendar, title="Blocked second")
        second = self.promote(sheets, calendar, another.record_id)
        self.assertEqual(second.status, "blocked"); self.assertEqual(calendar.insert_count, 1)

    def test_gates_block_before_consuming_authorization(self):
        cases = (
            ("approval", {"approval_status": "pending"}), ("status", {"status": "draft"}),
            ("title", {"event_title": ""}), ("missing-start", {"start": ""}),
            ("naive", {"start": "2026-07-12T09:00:00"}),
            ("end-before-start", {"end": "2026-07-12T08:00:00-06:00"}),
        )
        for label, fields in cases:
            with self.subTest(label=label):
                sheets, calendar = FakeSheets(), FakeCalendar(); draft = create_ready_draft(sheets, calendar, **fields)
                self.authorize(draft.record_id)
                result = self.promote(sheets, calendar, draft.record_id)
                self.assertEqual(result.status, "needs-info"); self.assertEqual(calendar.insert_count, 0); self.assertTrue(self.auth_path.exists())

    def test_public_calendar_allowance_blocks_one_shot_promotion_without_consuming_authorization(self):
        sheets, calendar = FakeSheets(), FakeCalendar()
        draft = create_ready_draft(sheets, calendar)
        tir.route_event_followup(
            sheets, calendar, f"id={draft.record_id} public_calendar_allowed=yes", SRC,
            allow_calendar_creation=False,
        )
        self.authorize(draft.record_id)

        result = self.promote(sheets, calendar, draft.record_id)

        self.assertEqual(result.status, "needs-info")
        self.assertEqual(calendar.insert_count, 0)
        self.assertTrue(self.auth_path.exists())

    def test_non_private_privacy_blocks_one_shot_promotion_without_consuming_authorization(self):
        sheets, calendar = FakeSheets(), FakeCalendar()
        draft = create_ready_draft(sheets, calendar, privacy_level="board-visible")
        self.authorize(draft.record_id)

        result = self.promote(sheets, calendar, draft.record_id)

        self.assertEqual(result.status, "needs-info")
        self.assertEqual(calendar.insert_count, 0)
        self.assertTrue(self.auth_path.exists())

    def test_public_export_excludes_private_created_event_and_daily_stays_zero_write(self):
        sheets, calendar = FakeSheets(), FakeCalendar(); draft = create_ready_draft(sheets, calendar, title="PRIVATE-EVENT-004")
        self.authorize(draft.record_id); self.promote(sheets, calendar, draft.record_id)
        rows = [ops.HEADERS["CalendarLog"]] + sheets.rows()
        self.assertEqual(sync.safe_calendar_export(rows, type("NoEvents", (), {"events": lambda _s: _s, "list": lambda _s, **_k: Result({"items": [{"id": "cal-1", "status": "confirmed"}]})})()), [])
        safe = {"EventDraftID": "EVT-PUBLIC-004", "CalendarEventID": "cal-public", "EventTitle": "PRIVATE", "EventType": "meeting", "StartDateTime": "2026-07-12T09:00:00+00:00", "EndDateTime": "2026-07-12T10:00:00+00:00", "Location": "PRIVATE", "Description": "PRIVATE", "Status": "ready", "PrivacyLevel": "board-visible", "PublicCalendarAllowed": "yes", "PublicTitle": "Public boundary", "PublicDescription": "Safe", "PublicLocation": "Hall", "ApprovalStatus": "approved"}
        public_rows = [ops.HEADERS["CalendarLog"], [safe.get(h, "") for h in ops.HEADERS["CalendarLog"]]]
        exported = sync.safe_calendar_export(public_rows, type("Events", (), {"events": lambda _s: _s, "list": lambda _s, **_k: Result({"items": [{"id": "cal-public", "status": "confirmed"}]})})())
        self.assertEqual(exported, [{"CalendarEventID": "cal-public", "EventTitle": "Public boundary", "EventType": "meeting", "StartDateTime": "2026-07-12T09:00:00+00:00", "EndDateTime": "2026-07-12T10:00:00+00:00", "Description": "Safe", "Location": "Hall", "Status": "ready"}])
        with patch.object(tir, "services", side_effect=AssertionError("daily write service")), patch.object(tir, "daily_services", return_value=(object(), object())), patch.object(tir.approved_safe_sync, "collect_approved_safe_data", return_value={"approved_needs": [], "approved_donations": [], "approved_reports": [], "approved_calendar": [], "approved_board_log": [], "approved_volunteer_gaps": []}):
            self.assertTrue(tir.handle_message("/daily").ok)


if __name__ == "__main__": unittest.main()
