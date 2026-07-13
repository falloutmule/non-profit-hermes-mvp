"""Offline fixtures for CLEANUP-007A record inventory classification."""
from __future__ import annotations

import importlib.util
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "inventory_live_test_records.py"


def load_inventory_module():
    if not MODULE_PATH.exists():
        return None
    spec = importlib.util.spec_from_file_location("cleanup007_inventory", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class LiveTestRecordInventoryTests(unittest.TestCase):
    def test_event_003_abandoned_synthetic_draft_requires_review(self):
        inventory = load_inventory_module()
        self.assertIsNotNone(inventory, "CLEANUP-007A inventory module is required")

        result = inventory.classify_records([{
            "EventDraftID": "EVT-FC5611E9",
            "EventTitle": "Safe fake EVENT-003 Telegram draft",
            "EventType": "telegram-test",
            "Status": "cancelled",
            "ApprovalStatus": "rejected",
            "CalendarEventID": "",
            "Notes": "EVENT-003 TEST RECORD - follow-up verified",
        }])

        self.assertEqual(result, [{
            "record_ref": "EVT-FC5611E9",
            "classification": "ABANDONED_DRAFT_REVIEW",
            "confidence": "high",
            "reason": "Explicit EVENT-003 synthetic draft is cancelled and rejected; retain for human review.",
        }])

    def test_event_004_complete_synthetic_evidence_is_retained(self):
        inventory = load_inventory_module()
        record = {
            "EventDraftID": "EVT-A31A0CF8",
            "EventTitle": "EVENT-004 SAFE FAKE CALENDAR PROMOTION TEST",
            "EventType": "event-004-test",
            "Status": "confirmed",
            "ApprovalStatus": "created",
            "CalendarEventID": "cpq3e1oivn4ajb4t8ktemjuj0g",
            "Description": "EVENT-004 SAFE FAKE CALENDAR TEST — synthetic record for controlled system verification only.",
        }

        result = inventory.classify_records([record])[0]

        self.assertEqual(result["classification"], "EVIDENCE_RETAIN")
        self.assertEqual(result["confidence"], "high")

    def test_explicit_active_synthetic_fixture_is_safe_fake_active(self):
        inventory = load_inventory_module()
        result = inventory.classify_records([{
            "RequestID": "REQ-TEST-ACTIVE-001",
            "NeedDescription": "Safe fake test request for regression coverage",
            "TestLifecycle": "active",
            "Status": "ready",
        }])[0]

        self.assertEqual(result["classification"], "SAFE_FAKE_ACTIVE")
        self.assertEqual(result["confidence"], "high")

    def test_explicit_historical_retention_marker_is_historical_retain(self):
        inventory = load_inventory_module()
        result = inventory.classify_records([{
            "ReportID": "REP-ARCHIVE-001",
            "Summary": "Completed pantry distribution summary",
            "RetentionDisposition": "historical-retain",
            "Status": "completed",
        }])[0]

        self.assertEqual(result["classification"], "HISTORICAL_RETAIN")
        self.assertEqual(result["confidence"], "high")

    def test_real_operational_record_is_do_not_touch_and_sensitive_values_are_not_output(self):
        inventory = load_inventory_module()
        record = {
            "DonationID": "DON-REAL-001",
            "ContactName": "Avery Example",
            "ContactEmail": "avery@example.org",
            "Phone": "+1-555-0100",
            "ItemDescription": "winter coats",
            "Status": "ready",
        }

        result = inventory.classify_records([record])[0]

        self.assertEqual(result["classification"], "REAL_OPERATIONAL_DO_NOT_TOUCH")
        output = json.dumps(result, sort_keys=True)
        self.assertNotIn("Avery Example", output)
        self.assertNotIn("avery@example.org", output)
        self.assertNotIn("+1-555-0100", output)

    def test_ambiguous_record_is_unknown_manual_review(self):
        inventory = load_inventory_module()
        result = inventory.classify_records([{
            "ReportID": "REP-UNRESOLVED-001",
            "Summary": "supplies distributed",
            "Status": "ready",
        }])[0]

        self.assertEqual(result["classification"], "UNKNOWN_MANUAL_REVIEW")
        self.assertEqual(result["confidence"], "low")

    def test_repeated_stable_identity_is_possible_duplicate_review(self):
        inventory = load_inventory_module()
        records = [
            {
                "DonationID": "DON-DUP-001",
                "ItemDescription": "coats",
                "Status": "new",
                "DuplicateReviewCandidate": True,
            },
            {
                "DonationID": "DON-DUP-001",
                "ItemDescription": "coats",
                "Status": "new",
                "DuplicateReviewCandidate": True,
            },
        ]

        result = inventory.classify_records(records)

        self.assertEqual([item["classification"] for item in result], [
            "POSSIBLE_DUPLICATE_REVIEW",
            "POSSIBLE_DUPLICATE_REVIEW",
        ])

    def test_duplicate_real_operational_records_remain_do_not_touch(self):
        inventory = load_inventory_module()
        records = [
            {"DonationID": "DON-REAL-DUP-001", "ContactName": "Avery Example", "DuplicateReviewCandidate": True},
            {"DonationID": "DON-REAL-DUP-001", "ContactName": "Avery Example", "DuplicateReviewCandidate": True},
        ]

        result = inventory.classify_records(records)

        self.assertEqual(
            [item["classification"] for item in result],
            ["REAL_OPERATIONAL_DO_NOT_TOUCH", "REAL_OPERATIONAL_DO_NOT_TOUCH"],
        )

    def test_duplicate_event_004_evidence_records_remain_evidence_retain(self):
        inventory = load_inventory_module()
        evidence = {
            "EventDraftID": "EVT-EVIDENCE-DUP-001",
            "EventTitle": "EVENT-004 SAFE FAKE CALENDAR PROMOTION TEST",
            "Status": "confirmed",
            "ApprovalStatus": "created",
            "CalendarEventID": "cpq3e1oivn4ajb4t8ktemjuj0g",
            "Description": "EVENT-004 SAFE FAKE CALENDAR TEST — synthetic record for controlled system verification only.",
            "DuplicateReviewCandidate": True,
        }

        result = inventory.classify_records([evidence, evidence.copy()])

        self.assertEqual(
            [item["classification"] for item in result],
            ["EVIDENCE_RETAIN", "EVIDENCE_RETAIN"],
        )

    def test_duplicate_historical_records_remain_historical_retain(self):
        inventory = load_inventory_module()
        historical = {
            "ReportID": "REP-HISTORICAL-DUP-001",
            "RetentionDisposition": "historical-retain",
            "Status": "completed",
            "DuplicateReviewCandidate": True,
        }

        result = inventory.classify_records([historical, historical.copy()])

        self.assertEqual(
            [item["classification"] for item in result],
            ["HISTORICAL_RETAIN", "HISTORICAL_RETAIN"],
        )

    def test_duplicate_ambiguous_records_remain_unknown_manual_review(self):
        inventory = load_inventory_module()
        ambiguous = {"ReportID": "REP-UNKNOWN-DUP-001", "Summary": "unclassified"}

        result = inventory.classify_records([ambiguous, ambiguous.copy()])

        self.assertEqual(
            [item["classification"] for item in result],
            ["UNKNOWN_MANUAL_REVIEW", "UNKNOWN_MANUAL_REVIEW"],
        )

    def test_vague_test_fake_or_sample_words_remain_unknown_manual_review(self):
        inventory = load_inventory_module()
        records = [
            {"ReportID": "REP-VAGUE-TEST-001", "Summary": "test"},
            {"ReportID": "REP-VAGUE-FAKE-001", "Summary": "fake"},
            {"ReportID": "REP-VAGUE-SAMPLE-001", "Summary": "sample"},
        ]

        result = inventory.classify_records(records)

        self.assertEqual(
            [item["classification"] for item in result],
            ["UNKNOWN_MANUAL_REVIEW", "UNKNOWN_MANUAL_REVIEW", "UNKNOWN_MANUAL_REVIEW"],
        )
        self.assertTrue(
            all(set(item) == {"record_ref", "classification", "confidence", "reason"} for item in result)
        )

    def test_classification_is_deterministic_and_does_not_mutate_inputs(self):
        inventory = load_inventory_module()
        records = [
            {"DonationID": "DON-DUP-002", "ItemDescription": "gloves", "Status": "new"},
            {"DonationID": "DON-DUP-002", "ItemDescription": "gloves", "Status": "new"},
            {"ReportID": "REP-UNRESOLVED-002", "Summary": "unknown history"},
        ]
        before = copy.deepcopy(records)

        first = inventory.classify_records(records)
        second = inventory.classify_records(records)

        self.assertEqual(first, second)
        self.assertEqual(records, before)
        self.assertEqual(
            set(first[0]), {"record_ref", "classification", "confidence", "reason"}
        )


if __name__ == "__main__":
    unittest.main()
