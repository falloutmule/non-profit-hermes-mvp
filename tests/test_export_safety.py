"""CLEANUP-002 export safety contract tests; all services are in-memory fakes."""
from __future__ import annotations

import importlib.util
import inspect
import sys
import unittest
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
    spec.loader.exec_module(module)
    return module


class _Result:
    def __init__(self, payload): self.payload = payload
    def execute(self): return self.payload


class _Values:
    def __init__(self, rows): self.rows, self.ranges = rows, []
    def get(self, **kwargs):
        self.ranges.append(kwargs["range"])
        return _Result({"values": self.rows})


class _Sheets:
    def __init__(self, rows): self._values = _Values(rows)
    def spreadsheets(self): return self
    def values(self): return self._values


class ExportSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sync = load_module("cleanup_sync", "scripts/sync_approved_safe_data.py")
        cls.schema = load_module("cleanup_schema", "scripts/non_profit_hermes_schema.py")

    def rows(self, tab, *mappings):
        header = self.schema.HEADERS[tab]
        return [header] + [[mapping.get(column, "") for column in header] for mapping in mappings]

    def request(self, record_id, **overrides):
        data = {"RequestID": record_id, "NeedDescription": "Safe food need", "NeedCategory": "food",
                "ConsentToShare": "yes", "PrivacyLevel": "board-visible", "Status": "ready",
                "LastUpdated": "2026-01-01T00:00:00+00:00"}
        data.update(overrides)
        return data

    def donation(self, record_id, **overrides):
        data = {"DonationID": record_id, "ItemDescription": "Coats", "DonationType": "clothing",
                "PrivacyLevel": "board-visible", "PublicListingAllowed": "yes", "Status": "ready",
                "LastUpdated": "2026-01-01T00:00:00+00:00"}
        data.update(overrides)
        return data

    def report(self, record_id, **overrides):
        data = {"ReportID": record_id, "ReportType": "pantry", "Summary": "PRIVATE",
                "PublicSummaryDraft": "Safe summary", "PublicSummaryAllowed": "yes",
                "PrivacyLevel": "board-visible", "Status": "ready",
                "LastUpdated": "2026-01-01T00:00:00+00:00"}
        data.update(overrides)
        return data

    def test_exact_status_allowlists_and_table_driven_denials(self):
        cases = [
            ("Requests", self.sync.safe_needs_from_requests, self.request, {"ready", "open", "in-progress", "published"}),
            ("Reports", self.sync.safe_reports, self.report, {"ready", "complete", "completed", "published"}),
            ("Donations", self.sync.safe_donations, self.donation, {"ready", "available", "received", "matched", "complete", "completed"}),
        ]
        denied = {"new", "draft", "needs-info", "private-review", "private-hold", "cancelled", "rejected"}
        for tab, exporter, factory, expected_allowed in cases:
            self.assertEqual(self.schema.PUBLIC_STATUS_BY_TYPE[tab], expected_allowed)
            for status in denied:
                with self.subTest(tab=tab, status=status):
                    self.assertEqual(exporter(self.rows(tab, factory(f"{tab}-{status}", Status=status))), [])
            for status in expected_allowed:
                with self.subTest(tab=tab, allowed=status):
                    self.assertEqual(len(exporter(self.rows(tab, factory(f"{tab}-{status}", Status=status)))), 1)

    def test_blank_consent_and_approval_fields_deny_export(self):
        self.assertEqual(self.sync.safe_needs_from_requests(self.rows("Requests", self.request("REQ-BLANK", ConsentToShare=""))), [])
        self.assertEqual(self.sync.safe_donations(self.rows("Donations", self.donation("DON-BLANK", PublicListingAllowed=""))), [])
        self.assertEqual(self.sync.safe_reports(self.rows("Reports", self.report("REP-BLANK", PublicSummaryAllowed=""))), [])

    def test_newer_private_or_needs_info_duplicate_suppresses_older_public_rows(self):
        examples = [
            ("Requests", self.sync.safe_needs_from_requests, self.request, "REQ-WRITE-TEST-001"),
            ("Donations", self.sync.safe_donations, self.donation, "DON-WRITE-TEST-001"),
            ("Reports", self.sync.safe_reports, self.report, "REP-WRITE-TEST-001"),
        ]
        for tab, exporter, factory, record_id in examples:
            with self.subTest(tab=tab, newer="private"):
                old = factory(record_id, LastUpdated="2026-01-01T00:00:00+00:00")
                new = factory(record_id, PrivacyLevel="private-review", LastUpdated="2026-01-02T00:00:00+00:00")
                self.assertEqual(exporter(self.rows(tab, old, new)), [])
            with self.subTest(tab=tab, newer="needs-info"):
                old = factory(record_id, LastUpdated="2026-01-01T00:00:00+00:00")
                new = factory(record_id, Status="needs-info", LastUpdated="2026-01-02T00:00:00+00:00")
                self.assertEqual(exporter(self.rows(tab, old, new)), [])

    def test_donations_and_reports_export_only_safe_fields(self):
        donation = self.sync.safe_donations(self.rows("Donations", self.donation("DON-SAFE", DonorContact="secret", Location="secret")))[0]
        self.assertEqual(set(donation), {"DonationID", "DateOffered", "DonationType", "ItemDescription", "Quantity", "Status", "ReceiptNeeded", "ThankYouNeeded"})
        report = self.sync.safe_reports(self.rows("Reports", self.report("REP-SAFE", Summary="raw private", PublicSummaryDraft="public only")))[0]
        self.assertEqual(report["Summary"], "public only")
        self.assertNotIn("SensitiveDetails", report)

    def test_full_range_reads_rows_101_150_final_and_ignores_trailing_empty(self):
        rows = self.rows("Requests", self.request("REQ-101"))
        rows.extend([[] for _ in range(48)])
        rows.append([self.request("REQ-150").get(column, "") for column in self.schema.HEADERS["Requests"]])
        rows.append([self.request("REQ-FINAL").get(column, "") for column in self.schema.HEADERS["Requests"]])
        rows.append([])
        svc = _Sheets(rows)
        read = self.sync.read_sheet_rows(svc, "Requests")
        exported = self.sync.safe_needs_from_requests(read)
        self.assertEqual({item["RequestID"] for item in exported}, {"REQ-101", "REQ-150", "REQ-FINAL"})
        self.assertEqual(svc._values.ranges, [self.schema.get_full_range("Requests")])
        self.assertNotIn("100", inspect.getsource(self.sync.read_sheet_rows))

    def test_board_log_is_aggregated_and_serializes_only_the_four_safe_fields(self):
        audit = self.rows("AuditLog",
            {"AuditID": "AUDIT-1", "Timestamp": "2026-01-01T10:00:00+00:00", "Action": "create", "TargetItem": "Donations/DON-WRITE-TEST-001"},
            {"AuditID": "AUDIT-2", "Timestamp": "2026-01-01T11:00:00+00:00", "Action": "create", "TargetItem": "Donations/DON-WRITE-TEST-001"},
            {"AuditID": "AUDIT-3", "Timestamp": "2026-01-01T12:00:00+00:00", "Action": "create", "TargetItem": "Tasks/TASK-PRIVATE"})
        entries = self.sync.safe_board_log(audit, set(), {"DON-WRITE-TEST-001"}, set())
        self.assertEqual(entries, [{"Date": "2026-01-01", "RecordType": "donation", "Action": "created", "Count": 2}])
        serialized = str(entries)
        for forbidden in ("AuditID", "TargetItem", "TASK-", "INV-", "EVT-", "REQ-", "DON-", "REP-", "CalendarEventID", "SourceMessageLink"):
            self.assertNotIn(forbidden, serialized)

    def test_hostile_html_fixture_escapes_exactly_and_never_leaks_tags(self):
        hostile = '<script>alert("x")</script> & "quoted" <b>bold</b>'
        escaped = '&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; &quot;quoted&quot; &lt;b&gt;bold&lt;/b&gt;'
        self.assertEqual(self.sync.esc(hostile), escaped)
        rendered = self.sync.render_page("safe", f"<p>{self.sync.esc(hostile)}</p>")
        self.assertIn(escaped, rendered)
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("<b>", rendered)

    def test_dry_run_expired_credentials_never_persist_and_reports_metrics(self):
        class ExpiredCredentials:
            expired = True
            refresh_token = "refresh-token"

            def refresh(self, _request):
                self.expired = False

            def to_json(self):
                return '{"token": "refreshed"}'

        rows = {tab: [self.schema.HEADERS[tab]] for tab in self.schema.TAB_ORDER}
        rows["Requests"] = self.rows(
            "Requests",
            self.request("REQ-OLD", LastUpdated="2026-01-01T00:00:00+00:00"),
            self.request("REQ-OLD", PrivacyLevel="private-review", LastUpdated="2026-01-02T00:00:00+00:00"),
            self.request("REQ-DENIED", ConsentToShare="no"),
        )
        rows["Requests"].extend([[] for _ in range(97)])
        rows["Requests"].append([self.request("REQ-101").get(column, "") for column in self.schema.HEADERS["Requests"]])
        output = __import__("io").StringIO()
        with __import__("contextlib").redirect_stdout(output), \
             patch.object(self.sync.Credentials, "from_authorized_user_file", return_value=ExpiredCredentials()), \
             patch.object(self.sync, "sheets_service", return_value=object()), \
             patch.object(self.sync, "calendar_service", return_value=object()), \
             patch.object(self.sync, "read_sheet_rows", side_effect=lambda _svc, tab: rows[tab]), \
             patch.object(self.sync, "safe_calendar_export", return_value=[]), \
             patch.object(Path, "write_text") as write_text, \
             patch.object(self.sync, "write_json") as write_json, \
             patch.object(self.sync, "build_pages") as build_pages:
            self.assertEqual(self.sync.run_sync(dry_run=True), 0)
        metrics = __import__("json").loads(output.getvalue())
        self.assertEqual(metrics["rows_read_by_tab"]["Requests"], 102)
        self.assertEqual(metrics["rows_after_row_100_by_tab"]["Requests"], 1)
        self.assertEqual(metrics["approved_counts"]["approved_needs"], 1)
        self.assertEqual(metrics["rejected_counts_by_reason"]["Requests"], {"consent_not_affirmative": 1, "privacy_not_approved": 1})
        self.assertEqual(metrics["duplicate_counts_by_tab"]["Requests"], 1)
        self.assertEqual(metrics["board_log_aggregate_count"], 0)
        self.assertEqual(metrics["filesystem_writes"], 0)
        write_text.assert_not_called()
        write_json.assert_not_called()
        build_pages.assert_not_called()

    def test_dry_run_help_exposes_mode(self):
        self.assertIn("--dry-run", __import__("subprocess").run([sys.executable, "scripts/sync_approved_safe_data.py", "--help"], cwd=ROOT, capture_output=True, text=True, check=True).stdout)


if __name__ == "__main__":
    unittest.main()
