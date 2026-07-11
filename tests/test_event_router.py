"""EVENT-003 draft-first /event router — strict TDD, all Google access faked.

Covers contract Tests 1-11:

  1. /event writes a Sheet-only EventDraft (EVT-XXXXXXXX); no Calendar insert;
     response says Calendar creation disabled pending EVENT-004; CalendarEventID blank.
  2. /event does NOT call create_calendar_event(); uses upsert_event_draft();
     explicit id=EVT-... / event_draft_id=... accepted; free text -> EventTitle
     when title absent; ambiguous free text preserved in Notes; no NL date inference.
  3. Active event state helpers store/restore active_event_id per-source without
     erasing other active_* ids; source_scope() preserves telegram:live mapping.
  4. event_row_by_draft_id / open_event_drafts / resolve_event_followup_target:
     find by EventDraftID; open states needs-info/draft/new/ready; terminal
     confirmed/cancelled/rejected; ambiguity lists EVT IDs; explicit id overrides.
  5. route_event_followup selects only with event-specific key or explicit EVT id;
     does not select on generic keys (title/description/status/notes/privacy_level)
     without active draft; does not intercept report/task/inventory/donation/need.
  6. Active pointer set on draft create when status in needs-info/draft/new/ready
     and CalendarEventID blank; kept when ready but not created; cleared only on
     confirmed+CalendarEventID, cancelled, or rejected.
  7. Time validation: offset/ Z ISO accepted; naive rejected (no UTC guess, no
     NL parse); phrase stored in notes; end may stay blank.
  8. Explicit promotion only via create_calendar=yes/confirm_create=yes; not merely
     because approved/ready; with False update fields, no backend, keep pointer,
     return disabled message; with True (fake) require approval + create, call
     create_calendar_event_from_draft, return EVT+Calendar ids, clear pointer.
  9. Telegram wording: never 'Event created' for Sheet-only draft; uses
     'Draft Event created: EVT-...', 'Calendar: not created', and disabled message.
 10. Plugin contract surface: live plugin calls repository router with
     source_link=telegram:6080816249, allow_calendar_creation=False, and never
     calls create_calendar_event / create_calendar_event_from_draft directly.
 11. /event default privacy private-review (internal when privacy_level=internal);
     PublicCalendarAllowed=no; no invented public fields.

No network, no live Google calls. Sheets/Calendar are in-memory fakes.
"""
from __future__ import annotations

import importlib.util
import re
import builtins
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


# Load router as a normal module (no google.auth side effects at import time here
# because we inject fakes and never call services()).
tir = load_module("event_router_test", "scripts/telegram_intake_router.py")
ops = load_module("event_ops_test", "scripts/non_profit_hermes_ops.py")


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
        rows = self.tabs.get("CalendarLog", [])
        return rows[1:] if rows else []

    def row_by_draft(self, draft_id: str) -> dict | None:
        header = ops.HEADERS["CalendarLog"]
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


SRC = "telegram:6080816249"


class EventRouterTests(unittest.TestCase):
    def setUp(self):
        # Isolate active-event / active-* state per test so shared state across
        # tests (e.g. an active pointer set in test_3) does not leak into others.
        import tempfile
        self._state_tmp = tempfile.NamedTemporaryFile(
            prefix="evt_state_", suffix=".json", delete=False
        )
        self._state_tmp.close()
        self._orig_state_path = tir.ACTIVE_NEED_STATE_PATH
        tir.ACTIVE_NEED_STATE_PATH = Path(self._state_tmp.name)

    def tearDown(self):
        tir.ACTIVE_NEED_STATE_PATH = self._orig_state_path
        try:
            Path(self._state_tmp.name).unlink()
        except FileNotFoundError:
            pass

    # ── Test 1: draft-only, no Calendar backend, disabled message ──
    def test_1_draft_only_no_calendar_and_disabled_message(self):
        sheets = FakeSheetsStore()
        cal = FakeCalendarService()
        res = tir.route_event(
            sheets, cal,
            {"event_title": "Board meeting", "start": "2026-07-12T09:00:00-06:00", "type": "meeting"},
            "", SRC, "private-review",
        )
        self.assertTrue(res.ok)
        self.assertTrue(res.record_id.startswith("EVT-"))
        # No Calendar insert happened.
        self.assertEqual(cal.insert_count, 0)
        # CalendarEventID blank.
        rec = sheets.row_by_draft(res.record_id)
        self.assertIsNotNone(rec)
        self.assertEqual(rec["CalendarEventID"], "")
        # Disabled message for EVENT-004.
        self.assertIn("Calendar creation is disabled pending EVENT-004", res.message)
        # Wording contract 9: never "Event created"; uses "Draft Event created".
        self.assertIn("Draft Event created", res.message)
        self.assertIn("Calendar: not created", res.message)
        self.assertNotIn("Event created", res.message.replace("Draft Event created", ""))

    # ── Test 2: upsert + explicit id + free text title + ambiguous notes ──
    def test_2_upsert_explicit_id_free_text_title_ambiguous_notes(self):
        sheets = FakeSheetsStore()
        cal = FakeCalendarService()
        # explicit id accepted
        res = tir.route_event(
            sheets, cal,
            {"event_draft_id": "EVT-EXPLICIT1", "event_title": "Named", "start": "2026-07-12T09:00:00-06:00"},
            "", SRC, "private-review",
        )
        self.assertEqual(res.record_id, "EVT-EXPLICIT1")
        self.assertEqual(sheets.row_by_draft("EVT-EXPLICIT1")["EventTitle"], "Named")

        # free text becomes EventTitle when title absent
        res2 = tir.route_event(
            sheets, cal, {}, "Saturday morning potluck", SRC, "private-review",
        )
        self.assertTrue(res2.record_id.startswith("EVT-"))
        rec = sheets.row_by_draft(res2.record_id)
        self.assertEqual(rec["EventTitle"], "Saturday morning potluck")
        # ambiguous free text preserved in Notes (no NL date inference)
        self.assertIn("Saturday morning potluck", rec["Notes"])
        self.assertEqual(rec["StartDateTime"], "")  # not inferred

    # ── Test 3: active event state helpers + per-source isolation ──
    def test_3_active_event_state_helpers_preserve_other_ids(self):
        # Build an active need pointer in the same scope to ensure it is not erased.
        tir.set_active_need_request_id(SRC, "REQ-OTHER")
        self.assertEqual(tir.get_active_need_request_id(SRC), "REQ-OTHER")

        tir.set_active_event_id(SRC, "EVT-ABC")
        self.assertEqual(tir.get_active_event_id(SRC), "EVT-ABC")
        # other id untouched
        self.assertEqual(tir.get_active_need_request_id(SRC), "REQ-OTHER")

        # scope normalization (telegram:live -> telegram:6080816249)
        self.assertEqual(tir.source_scope("telegram:live"), "telegram:6080816249")
        tir.set_active_event_id("telegram:live", "EVT-LIVE")
        self.assertEqual(tir.get_active_event_id(SRC), "EVT-LIVE")
        self.assertEqual(tir.get_active_need_request_id(SRC), "REQ-OTHER")

        tir.clear_active_event_id(SRC, "EVT-LIVE")
        self.assertEqual(tir.get_active_event_id(SRC), "")
        self.assertEqual(tir.get_active_need_request_id(SRC), "REQ-OTHER")  # not erased

    # ── Test 4: row/resolve helpers ──
    def test_4_row_and_resolve_helpers(self):
        sheets = FakeSheetsStore()
        cal = FakeCalendarService()
        # Create three drafts in same source.
        created = []
        for i in range(3):
            r = tir.route_event(
                sheets, cal,
                {"event_title": f"Evt{i}", "start": "2026-07-12T09:00:00-06:00", "status": "needs-info"},
                "", SRC, "private-review",
            )
            created.append(r.record_id)
        # Force one to a terminal state (confirmed) via direct backend update.
        ops.upsert_event_draft(sheets, event_draft_id=created[0], status="confirmed")
        open_ids = {d["EventDraftID"] for d in tir.open_event_drafts(sheets, SRC)}
        self.assertNotIn(created[0], open_ids)
        self.assertIn(created[1], open_ids)
        self.assertIn(created[2], open_ids)

        # resolve by explicit id overrides active pointer
        tir.set_active_event_id(SRC, created[1])
        row, problems = tir.resolve_event_followup_target(sheets, SRC, {"id": created[2]})
        self.assertEqual(row["EventDraftID"], created[2])
        self.assertEqual(problems, [])

        # Multiple open drafts without explicit id -> ambiguity response
        tir.clear_active_event_id(SRC)
        row2, problems2 = tir.resolve_event_followup_target(sheets, SRC, {})
        self.assertIsNone(row2)
        self.assertTrue(any("multiple active event drafts" in p for p in problems2))

    # ── Test 5: followup selection rules ──
    def test_5_followup_selection_rules(self):
        sheets = FakeSheetsStore()
        cal = FakeCalendarService()
        # No active draft, generic keys only -> must NOT select event handler.
        # (route_event_followup returns None so handle_message falls through.)
        self.assertIsNone(
            tir.route_event_followup(sheets, cal, "title=SomeOther status=ready", SRC, allow_calendar_creation=False)
        )

        # Create an active draft, then generic keys should now attach to it.
        tir.route_event(sheets, cal, {"event_title": "Active", "start": "2026-07-12T09:00:00-06:00"}, "", SRC, "private-review")
        attached = tir.route_event_followup(sheets, cal, "title=ActiveRenamed location=Hall", SRC, allow_calendar_creation=False)
        self.assertIsNotNone(attached)
        self.assertTrue(attached.record_id.startswith("EVT-"))

        # Must not intercept other command follow-ups.
        self.assertIsNone(tir.route_event_followup(sheets, cal, "/report pantry summary=x", SRC, allow_calendar_creation=False))
        self.assertIsNone(tir.route_event_followup(sheets, cal, "task=TASK-1 title=do", SRC, allow_calendar_creation=False))
        self.assertIsNone(tir.route_event_followup(sheets, cal, "donation=DON-1 item=hat", SRC, allow_calendar_creation=False))
        self.assertIsNone(tir.route_event_followup(sheets, cal, "need=REQ-1 description=foo", SRC, allow_calendar_creation=False))
        self.assertIsNone(tir.route_event_followup(sheets, cal, "inventory=INV-1 item=socks", SRC, allow_calendar_creation=False))

    # ── Test 6: active pointer lifecycle ──
    def test_6_active_pointer_lifecycle(self):
        sheets = FakeSheetsStore()
        cal = FakeCalendarService()
        # Set on draft create (needs-info).
        r = tir.route_event(sheets, cal, {"event_title": "P", "start": "2026-07-12T09:00:00-06:00"}, "", SRC, "private-review")
        self.assertEqual(tir.get_active_event_id(SRC), r.record_id)
        # Kept when ready but not created.
        tir.route_event_followup(sheets, cal, f"status=ready id={r.record_id}", SRC, allow_calendar_creation=False)
        self.assertEqual(tir.get_active_event_id(SRC), r.record_id)
        # Cleared on cancelled.
        tir.route_event_followup(sheets, cal, f"status=cancelled id={r.record_id}", SRC, allow_calendar_creation=False)
        self.assertEqual(tir.get_active_event_id(SRC), "")
        # Re-create and clear on rejected.
        r2 = tir.route_event(sheets, cal, {"event_title": "Q", "start": "2026-07-12T09:00:00-06:00"}, "", SRC, "private-review")
        tir.route_event_followup(sheets, cal, f"status=rejected id={r2.record_id}", SRC, allow_calendar_creation=False)
        self.assertEqual(tir.get_active_event_id(SRC), "")
        # Cleared when confirmed + CalendarEventID populated (promotion path).
        r3 = tir.route_event(sheets, cal, {"event_title": "R", "start": "2026-07-12T09:00:00-06:00", "approval_status": "approved", "status": "ready"}, "", SRC, "private-review")
        tir.route_event_followup(sheets, cal, f"create_calendar=yes id={r3.record_id}", SRC, allow_calendar_creation=True)
        self.assertEqual(tir.get_active_event_id(SRC), "")

    # ── Test 7: time validation ──
    def test_7_time_validation_naive_rejected_end_blank(self):
        sheets = FakeSheetsStore()
        cal = FakeCalendarService()
        # Naive ISO rejected; phrase preserved in Notes; needs-info.
        r = tir.route_event(sheets, cal, {"event_title": "Naive", "start": "2026-07-12T09:00:00"}, "", SRC, "private-review")
        self.assertEqual(r.status, "needs-info")
        rec = sheets.row_by_draft(r.record_id)
        self.assertEqual(rec["StartDateTime"], "")  # not written
        self.assertIn("Unparsed time phrase", rec["Notes"])
        self.assertIn("2026-07-12T09:00:00", rec["Notes"])

        # Offset ISO accepted; end may stay blank.
        r2 = tir.route_event(sheets, cal, {"event_title": "Offset", "start": "2026-07-12T09:00:00Z"}, "", SRC, "private-review")
        rec2 = sheets.row_by_draft(r2.record_id)
        self.assertEqual(rec2["StartDateTime"], "2026-07-12T09:00:00+00:00")
        self.assertEqual(rec2["EndDateTime"], "")

        # 'Saturday morning' natural language -> not inferred, stored in Notes.
        r3 = tir.route_event(sheets, cal, {}, "Saturday morning potluck", SRC, "private-review")
        rec3 = sheets.row_by_draft(r3.record_id)
        self.assertEqual(rec3["StartDateTime"], "")
        self.assertIn("Saturday morning potluck", rec3["Notes"])

    # ── Test 8: explicit promotion only ──
    def test_8_explicit_promotion_only(self):
        sheets = FakeSheetsStore()
        cal = FakeCalendarService()
        # ready + approved but NO promote flag -> still draft-only, pointer kept.
        r = tir.route_event(sheets, cal, {"event_title": "Promo", "start": "2026-07-12T09:00:00-06:00", "approval_status": "approved", "status": "ready"}, "", SRC, "private-review")
        self.assertEqual(cal.insert_count, 0)
        self.assertEqual(tir.get_active_event_id(SRC), r.record_id)
        self.assertIn("Calendar creation is disabled pending EVENT-004", r.message)

        # Disabled promotion with create_calendar=yes -> update fields, keep pointer, no backend.
        r2 = tir.route_event_followup(sheets, cal, f"create_calendar=yes id={r.record_id} event_title=Renamed", SRC, allow_calendar_creation=False)
        self.assertEqual(cal.insert_count, 0)
        self.assertEqual(tir.get_active_event_id(SRC), r.record_id)
        self.assertEqual(sheets.row_by_draft(r.record_id)["EventTitle"], "Renamed")
        self.assertIn("Calendar creation is disabled pending EVENT-004", r2.message)

        # Fake-test promotion (allow_calendar_creation=True) -> requires approval + create.
        r3 = tir.route_event_followup(sheets, cal, f"create_calendar=yes id={r.record_id}", SRC, allow_calendar_creation=True)
        self.assertEqual(r3.status, "confirmed")
        self.assertTrue(r3.calendar_event_id.startswith("cal-"))
        self.assertEqual(cal.insert_count, 1)
        self.assertEqual(tir.get_active_event_id(SRC), "")  # pointer cleared
        self.assertEqual(sheets.row_by_draft(r.record_id)["CalendarEventID"], r3.calendar_event_id)

        # Repeating the same explicit router promotion is idempotent: return the
        # existing ID without another Calendar insert or CalendarLog row.
        r4 = tir.route_event_followup(sheets, cal, f"create_calendar=yes id={r.record_id}", SRC, allow_calendar_creation=True)
        self.assertEqual(r4.status, "confirmed")
        self.assertEqual(r4.backend_status, "already_created")
        self.assertEqual(r4.calendar_event_id, r3.calendar_event_id)
        self.assertEqual(cal.insert_count, 1)
        self.assertEqual(len(sheets.calendar_log_rows()), 1)
        self.assertEqual(sheets.row_by_draft(r.record_id)["CalendarEventID"], r3.calendar_event_id)

    # ── Test 9: wording (subset asserted in test_1; add explicit assertions) ──
    def test_9_wording_sheet_only(self):
        sheets = FakeSheetsStore()
        cal = FakeCalendarService()
        r = tir.route_event(sheets, cal, {"event_title": "Wording", "start": "2026-07-12T09:00:00-06:00"}, "", SRC, "private-review")
        self.assertIn("Draft Event created:", r.message)
        self.assertIn("Calendar: not created", r.message)
        self.assertIn("Calendar creation is disabled pending EVENT-004.", r.message)
        # never the banned phrase on its own line
        self.assertNotRegex(r.message, r"(?m)^Event created")

    def test_9_plugin_renderer_sloppy_needs_info_is_draft_safe(self):
        sheets = FakeSheetsStore()
        cal = FakeCalendarService()
        text = tir._result_to_text(
            tir.route_event(sheets, cal, {}, "Saturday morning potluck", SRC, "private-review")
        )
        self.assertRegex(text, r"(?m)^Draft Event created: EVT-")
        self.assertIn("Privacy: private-review", text)
        self.assertIn("Status: needs-info", text)
        self.assertIn("Calendar: not created", text)
        self.assertIn("Calendar creation is disabled pending EVENT-004.", text)
        self.assertNotRegex(text, r"(?m)^Event created")

    def test_9_plugin_renderer_structured_new_is_draft_safe(self):
        sheets = FakeSheetsStore()
        cal = FakeCalendarService()
        text = tir._result_to_text(
            tir.route_event(
                sheets,
                cal,
                {"title": "Structured", "start": "2026-07-12T09:00:00-06:00"},
                "",
                SRC,
                "private-review",
            )
        )
        self.assertRegex(text, r"(?m)^Draft Event created: EVT-")
        self.assertIn("Privacy: private-review", text)
        self.assertIn("Status: new", text)
        self.assertIn("Calendar: not created", text)
        self.assertIn("Calendar creation is disabled pending EVENT-004.", text)
        self.assertNotRegex(text, r"(?m)^Event created")

    # ── Test 10: plugin contract surface (live plugin script) ──
    def test_10_plugin_contract_surface(self):
        plugin_path = Path.home() / "AppData" / "Local" / "hermes" / "plugins" / "non-profit-hermes-event" / "__init__.py"
        self.assertTrue(plugin_path.exists(), "event plugin __init__.py must exist")
        src = plugin_path.read_text(encoding="utf-8")
        # registers /event
        self.assertTrue('register_command("event"' in src or "register_command('event'" in src)
        # passes source_link telegram:6080816249
        self.assertIn("telegram:6080816249", src)
        # never calls calendar create functions directly
        self.assertNotIn("create_calendar_event(", src)
        self.assertNotIn("create_calendar_event_from_draft(", src)
        # explicitly locks the live invocation to draft-only mode
        self.assertRegex(src, r"allow_calendar_creation\s*=\s*False")
        self.assertNotRegex(src, r"allow_calendar_creation\s*=\s*True")

    def test_10_actual_plugin_event_invocation_is_offline_and_draft_only(self):
        plugin_path = Path.home() / "AppData" / "Local" / "hermes" / "plugins" / "non-profit-hermes-event" / "__init__.py"
        plugin = load_module("event_plugin_offline_test", str(plugin_path))
        captured: dict[str, object] = {}
        sentinel = object()
        rendered = (
            "Draft Event created: EVT-OFFLINE1\n"
            "Privacy: private-review\n"
            "Status: needs-info\n"
            "Calendar: not created\n"
            "Calendar creation is disabled pending EVENT-004."
        )

        fake_router = types.ModuleType("telegram_intake_router")

        def fake_handle_message(message: str, **kwargs):
            captured["message"] = message
            captured.update(kwargs)
            return sentinel

        def fake_result_to_text(result):
            self.assertIs(result, sentinel)
            return rendered

        fake_router.handle_message = fake_handle_message
        fake_router._result_to_text = fake_result_to_text
        original_import = builtins.__import__

        def offline_import(name, *args, **kwargs):
            if name == "telegram_intake_router":
                return fake_router
            return original_import(name, *args, **kwargs)

        # Invoke the external plugin's real _event handler. Its router import is
        # intercepted in-memory, so no Google, Telegram, gateway, or network path
        # can be reached by this test.
        with mock.patch("builtins.__import__", side_effect=offline_import):
            text = plugin._event('event_title="Offline only"')

        self.assertEqual(captured["message"], '/event event_title="Offline only"')
        self.assertEqual(captured["source_link"], "telegram:6080816249")
        self.assertIs(captured["allow_calendar_creation"], False)
        self.assertEqual(text, rendered)
        self.assertRegex(text, r"(?m)^Draft Event created: EVT-OFFLINE1$")
        self.assertIn("Calendar: not created", text)
        self.assertIn("Calendar creation is disabled pending EVENT-004.", text)
        self.assertNotRegex(text, r"(?m)^Event created")

    # ── Test 11: default privacy + no invented public fields ──
    def test_11_default_privacy_no_invented_public(self):
        sheets = FakeSheetsStore()
        cal = FakeCalendarService()
        r = tir.route_event(sheets, cal, {"event_title": "Priv", "start": "2026-07-12T09:00:00-06:00"}, "", SRC, "private-review")
        rec = sheets.row_by_draft(r.record_id)
        self.assertEqual(rec["PrivacyLevel"], "private-review")
        self.assertEqual(rec["PublicCalendarAllowed"], "no")
        # No invented public fields.
        self.assertEqual(rec["PublicTitle"], "")
        self.assertEqual(rec["PublicDescription"], "")
        self.assertEqual(rec["PublicLocation"], "")

        # internal privacy when privacy_level=internal
        r2 = tir.route_event(sheets, cal, {"event_title": "Int", "start": "2026-07-12T09:00:00-06:00", "privacy_level": "internal"}, "", SRC, "internal")
        self.assertEqual(sheets.row_by_draft(r2.record_id)["PrivacyLevel"], "internal")


if __name__ == "__main__":
    unittest.main()
