# CLEANUP-002 Export Safety Report

## Canonical outcome

CLEANUP-002 is complete. Its implementation commit is `9626aaa23cb390493290edc7e92d2e048d80bab7` (`fix: unify schemas and harden approved-safe exports`), and its closeout commit is `0bae419c0f7f6173beb0545c163cc9e1d0d028c1`.

Query the current Git revision with `git rev-parse HEAD` and the current remote `main` revision with `git ls-remote origin refs/heads/main`.

The implementation scope was exactly these seven files:

1. `CLEANUP_002_EXPORT_SAFETY_REPORT.md`
2. `scripts/non_profit_hermes_ops.py`
3. `scripts/non_profit_hermes_schema.py`
4. `scripts/sync_approved_safe_data.py`
5. `scripts/telegram_intake_router.py`
6. `tests/test_export_safety.py`
7. `tests/test_schema_parity.py`

No Calendar event was created, edited, or deleted by CLEANUP-002. EVENT-004 remains unstarted and blocked; this cleanup did not enable Calendar promotion, activate a plugin, refresh or restart a gateway, register Telegram behavior, or perform a live Telegram test.

## Implemented controls

- `scripts/non_profit_hermes_schema.py` is the canonical owner of the Sheet headers used by writer and export paths.
- The Reports and Donations fields were appended without changing existing data-row values: `Reports!V1 = PublicSummaryAllowed`; `Donations!V1:X1 = PrivacyLevel, PublicListingAllowed, LastUpdated`.
- Full-range reads eliminate the former row-100 truncation.
- Export deduplication uses the canonical primary key and newest `LastUpdated` before publication gates. A newer private or `needs-info` duplicate suppresses an older publishable row.
- Requests require approved privacy, an exact public status, and affirmative `ConsentToShare`.
- Donations require approved privacy, an exact public status, and affirmative `PublicListingAllowed`.
- Reports require approved privacy, an exact public status, affirmative `PublicSummaryAllowed`, and a non-empty `PublicSummaryDraft`; exports use that public draft and never raw `Summary` or `SensitiveDetails`.
- User-controlled values are HTML-escaped in generated public HTML.
- Board-log output is aggregate-only (`Date`, `RecordType`, `Action`, `Count`) and excludes internal record and audit identifiers.

Approved privacy levels are `board-visible`, `public-safe`, and `board-visible-test`. Affirmative values are exactly `yes`, `true`, `1`, and `approved` after case/whitespace normalization; blank or non-affirmative values deny export. Tasks and Inventory have no public status and are not exported.

## Verification evidence

Post-repair independent implementation checker: **PASS**, recorded 2026-07-11 13:48:15 MDT.

Local verification completed:

- `python -m pytest tests/test_schema_parity.py -q` — `9 passed in 0.13s`
- `python -m pytest tests/test_export_safety.py -q` — `9 passed, 41 subtests passed in 0.33s`
- `python -m pytest tests/test_event_router.py -q` — `14 passed in 0.20s`
- `python -m pytest tests/test_event_draft_backend.py -q` — `13 passed, 6 subtests passed in 0.12s`
- `python -m pytest tests/test_event_calendar_privacy.py -q` — `8 passed, 5 subtests passed in 0.12s`
- `python -m pytest -q` — `53 passed, 52 subtests passed in 0.45s`
- `python -m py_compile scripts/*.py tests/*.py` — passed
- `git diff --check` — passed (with the existing line-ending warning for `scripts/sync_approved_safe_data.py`)

The controlled credential-backed `--dry-run` read full Sheet ranges, made zero filesystem writes, and created no Calendar events. Its evidence was:

| Metric | Result |
| --- | --- |
| Rows read | Requests 12; Donations 7; Reports 23; Tasks 10; Inventory 8; CalendarLog 13; AuditLog 108 |
| Rows after row 100 | AuditLog 8 |
| Approved counts | needs 0; donations 0; reports 0; calendar 0; board log 11 |
| Requests rejections | `consent_not_affirmative` 4; `privacy_not_approved` 2; `status_not_public` 4 |
| Donations rejections | `privacy_not_approved` 5 |
| Reports rejections | `privacy_not_approved` 11; `public_summary_not_affirmative` 7; `status_not_public` 3 |
| Calendar rejections | `missing_calendar_event_id` 8 |
| Duplicate counts | Requests 1; Donations 1; Reports 1; Tasks 1; Inventory 1; AuditLog 0; CalendarLog 0 |
| Filesystem writes | 0 |

This is live read-only dry-run evidence. It proves no export files/pages were written by that run; it does not claim a live approved record was exported because all approved export counts were zero.

The header-only migration preserved data rows. Pre/post data-row equality and SHA-256 evidence: Reports (22 rows) `2c5ee26fb233f92be8225a8ed0b9df53512976924955c91c7823517dc6367132`; Donations (6 rows) `474419f4863dccaa87c8a9ee733e84db78187e39ee46e77c0d3d3c38df0071e0`.

The four generated JSON files — `docs/data/approved_board_log.json`, `docs/data/approved_donations.json`, `docs/data/approved_needs.json`, and `docs/data/approved_reports.json` — were inspected and then restored because no public snapshot publication was authorized. No automatic approval backfill occurred.

## Remaining boundary

CLEANUP-003 is next. The remaining P0 concern is that `/daily` still couples a daily summary invocation to generation behavior. Publication remains frozen until CLEANUP-003 separates `/daily` from generation. There is no authorized public snapshot update and no automatic approval backfill.
