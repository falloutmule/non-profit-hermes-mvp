"""CLEANUP-003 daily summaries must use an approved-safe in-memory snapshot."""
from __future__ import annotations

import builtins
import hashlib
import importlib.util
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class _Result:
    def __init__(self, payload): self.payload = payload
    def execute(self): return self.payload


class FakeSheets:
    def __init__(self, rows_by_tab): self.rows_by_tab = rows_by_tab
    def spreadsheets(self): return self
    def values(self): return self
    def get(self, **kwargs):
        tab = kwargs["range"].split("!", 1)[0]
        return _Result({"values": self.rows_by_tab.get(tab, [])})


class FakeCalendar:
    def __init__(self, events): self.events_data = events
    def events(self): return self
    def list(self, **_kwargs): return _Result({"items": self.events_data})


class DailyReadOnlyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sync = load_module("cleanup003_sync", "scripts/sync_approved_safe_data.py")
        cls.router = load_module("cleanup003_router", "scripts/telegram_intake_router.py")

    def rows(self, tab, *mappings):
        header = self.sync.HEADERS[tab]
        return [header] + [[mapping.get(column, "") for column in header] for mapping in mappings]

    def fake_services(self):
        rows = {tab: [self.sync.HEADERS[tab]] for tab in self.sync.TAB_ORDER}
        rows["Requests"] = self.rows("Requests", {
            "RequestID": "REQ-SAFE-1", "NeedDescription": "Blankets", "NeedCategory": "supplies",
            "Urgency": "urgent", "ConsentToShare": "yes", "PrivacyLevel": "board-visible",
            "Status": "ready", "NextAction": "call coordinator",
        })
        rows["Donations"] = self.rows("Donations", {
            "DonationID": "DON-SAFE-1", "ItemDescription": "Coats", "DonationType": "clothing",
            "PublicListingAllowed": "yes", "PrivacyLevel": "board-visible", "Status": "ready",
        })
        rows["Reports"] = self.rows("Reports", {
            "ReportID": "REP-SAFE-1", "ReportType": "pantry", "PublicSummaryDraft": "Supplies distributed",
            "PublicSummaryAllowed": "yes", "PrivacyLevel": "board-visible", "Status": "ready",
        })
        rows["CalendarLog"] = self.rows("CalendarLog", {
            "EventDraftID": "EVT-SAFE-1", "CalendarEventID": "evt-safe-1", "PublicTitle": "Pantry hours", "EventType": "service",
            "StartDateTime": "2026-07-11T09:00:00+00:00", "EndDateTime": "2026-07-11T10:00:00+00:00",
            "PublicCalendarAllowed": "yes", "ApprovalStatus": "approved", "PrivacyLevel": "board-visible", "Status": "ready",
        })
        return FakeSheets(rows), FakeCalendar([{"id": "evt-safe-1", "status": "confirmed"}])

    def test_daily_uses_in_memory_safe_snapshot_without_public_generation_or_docs_changes(self):
        sheets, calendar = self.fake_services()
        with tempfile.TemporaryDirectory() as temp:
            docs = Path(temp) / "docs"
            docs.mkdir()
            sentinel = docs / "existing.json"
            sentinel.write_text('{"unchanged": true}\n', encoding="utf-8")
            before = {path.relative_to(docs): hashlib.sha256(path.read_bytes()).hexdigest() for path in docs.rglob("*") if path.is_file()}
            original_open = builtins.open
            def reject_writable_open(*args, **kwargs):
                mode = kwargs.get("mode", args[1] if len(args) > 1 else "r")
                if any(flag in mode for flag in "wax+"):
                    raise AssertionError("daily opened a file for writing")
                return original_open(*args, **kwargs)
            with (
                patch.object(builtins, "open", side_effect=reject_writable_open),
                patch.object(Path, "write_text", side_effect=AssertionError("daily wrote a file")),
                patch.object(Path, "touch", side_effect=AssertionError("daily touched a file")),
                patch.object(self.router.approved_safe_sync, "write_json", side_effect=AssertionError("daily generated JSON")),
                patch.object(self.router.approved_safe_sync, "write_page", side_effect=AssertionError("daily generated HTML")),
                patch.object(self.router.approved_safe_sync, "write_both", side_effect=AssertionError("daily generated page")),
                patch.object(self.router, "now_utc", return_value=datetime(2026, 7, 11, tzinfo=timezone.utc)),
            ):
                summary = self.router.run_daily_summary(sheets, calendar)
            after = {path.relative_to(docs): hashlib.sha256(path.read_bytes()).hexdigest() for path in docs.rglob("*") if path.is_file()}

        self.assertEqual(after, before)
        for section in (
            "Today's calendar:", "Open urgent requests:", "Donation pickups/drop-offs:",
            "Volunteer gaps:", "Inventory shortages:", "Approved-safe reports:",
            "Completed items since last brief:", "Website:",
        ):
            self.assertIn(section, summary)
        self.assertIn("Pantry hours (ready)", summary)
        self.assertIn("REQ-SAFE-1: Blankets", summary)
        self.assertIn("DON-SAFE-1: Coats", summary)
    def test_explicit_writer_generates_json_html_nojekyll_and_retained_report_only_in_temp_docs(self):
        sheets, calendar = self.fake_services()
        snapshot = self.sync.collect_approved_safe_data(sheets, calendar)
        with tempfile.TemporaryDirectory() as temp:
            docs = Path(temp) / "docs"
            self.sync.write_public_site(snapshot, docs_dir=docs)
            expected = {
                "data/approved_needs.json", "data/approved_calendar.json", "data/approved_reports.json",
                "data/approved_donations.json", "data/approved_volunteer_gaps.json", "data/approved_board_log.json",
                ".nojekyll", "index.html", "index/index.html", "reports.html", "reports/index.html",
                "LIVE_CHECK_002.html",
            }
            files = {path.relative_to(docs).as_posix() for path in docs.rglob("*") if path.is_file()}
        self.assertTrue(expected <= files)

    def test_dry_run_is_zero_write_even_with_fake_services(self):
        sheets, calendar = self.fake_services()
        with (
            patch.object(self.sync, "creds", return_value=object()),
            patch.object(self.sync, "sheets_service", return_value=sheets),
            patch.object(self.sync, "calendar_service", return_value=calendar),
            patch.object(Path, "write_text", side_effect=AssertionError("dry run wrote a file")),
            patch.object(Path, "touch", side_effect=AssertionError("dry run touched a file")),
            patch.object(self.sync, "write_json", side_effect=AssertionError("dry run generated JSON")),
            patch.object(self.sync, "write_page", side_effect=AssertionError("dry run generated HTML")),
            patch.object(self.sync, "write_both", side_effect=AssertionError("dry run generated page")),
        ):
            self.assertEqual(self.sync.run_sync(dry_run=True), 0)

    def test_daily_command_succeeds_when_all_public_generation_functions_raise(self):
        sheets, calendar = self.fake_services()
        with (
            patch.object(self.router, "daily_services", return_value=(sheets, calendar)),
            patch.object(self.router.approved_safe_sync, "write_json", side_effect=AssertionError("public generation called")),
            patch.object(self.router.approved_safe_sync, "write_page", side_effect=AssertionError("public generation called")),
            patch.object(self.router.approved_safe_sync, "write_both", side_effect=AssertionError("public generation called")),
            patch.object(self.router, "services", side_effect=AssertionError("/daily initialized write services")),
        ):
            result = self.router.handle_message("/daily")
        self.assertTrue(result.ok)
        self.assertEqual(
            result.message,
            "Read-only in-memory board-safe summary; no public files were generated.",
        )
        self.assertIn("Daily board-safe summary", result.summary)

    def test_daily_uses_the_same_gated_data_as_shared_collection(self):
        sheets, calendar = self.fake_services()
        private = {column: "" for column in self.sync.HEADERS["Requests"]}
        private.update({"RequestID": "REQ-PRIVATE", "NeedDescription": "PRIVATE SENTINEL", "ConsentToShare": "yes", "PrivacyLevel": "private-review", "Status": "ready"})
        sheets.rows_by_tab["Requests"].append([private[column] for column in self.sync.HEADERS["Requests"]])
        expected = self.sync.collect_approved_safe_data(sheets, calendar)
        summary = self.router.run_daily_summary(sheets, calendar)
        self.assertEqual({item["RequestID"] for item in expected["approved_needs"]}, {"REQ-SAFE-1"})
        self.assertIn("REQ-SAFE-1", summary)
        self.assertNotIn("PRIVATE SENTINEL", summary)


if __name__ == "__main__":
    unittest.main()
