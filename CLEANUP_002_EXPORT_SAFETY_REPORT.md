# CLEANUP-002 Export Safety Report

## Outcome

CLEANUP-002 establishes a canonical Sheet schema and deny-by-default approved-safe exports. Local verification passes. The controlled credential-backed live sync dry-run and the live header-only migration both completed without creating Calendar events or changing Sheet data rows.

## Starting point and scope

- Starting baseline: `d58b86f3fb2fcb806f9ad547482c012902599655` (`docs: finish canonical documentation reconciliation`).
- Permitted modification for this handoff: this report only.
- No Calendar events were created, edited, or deleted.
- No gateway, plugin, Telegram, EVENT-004, commit, or push action was performed.

## Final local verification

Commands run after the CLEANUP-002 schema append-order repair:

- `python -m pytest tests/test_schema_parity.py -q` — `9 passed in 0.13s`
- `python -m pytest tests/test_export_safety.py -q` — `9 passed, 41 subtests passed in 0.33s`
- `python -m pytest tests/test_event_router.py -q` — `14 passed in 0.20s`
- `python -m pytest tests/test_event_draft_backend.py -q` — `13 passed, 6 subtests passed in 0.12s`
- `python -m pytest tests/test_event_calendar_privacy.py -q` — `8 passed, 5 subtests passed in 0.12s`
- `python -m pytest -q` — `53 passed, 52 subtests passed in 0.45s`
- `python -m py_compile scripts/*.py tests/*.py` — passed
- `git diff --check` — passed (Git emitted only the existing line-ending warning for `scripts/sync_approved_safe_data.py`.)

## Canonical schema and export safety controls

- `scripts/non_profit_hermes_schema.py` is the canonical owner of `HEADERS`; both writer and export paths import it.
- New schema fields are append-only. The live header update appended `Reports!V1 = PublicSummaryAllowed` and `Donations!V1:X1 = PrivacyLevel, PublicListingAllowed, LastUpdated`.
- Exports deduplicate by canonical primary key and newest `LastUpdated` **before** publication gates. A newer private or `needs-info` duplicate suppresses an older publishable row.
- Approved privacy levels are exactly `board-visible`, `public-safe`, and `board-visible-test`.
- Affirmative fields accept exactly `yes`, `true`, `1`, and `approved` (case/whitespace normalized); blank or non-affirmative consent/approval denies export.
- Public status allowlists are exact:
  - Requests: `ready`, `open`, `in-progress`, `published`.
  - Donations: `ready`, `available`, `received`, `matched`, `complete`, `completed`.
  - Reports: `ready`, `complete`, `completed`, `published`.
  - Tasks and Inventory: no public statuses.
- Terminal/never-public statuses are exactly `cancelled`, `rejected`, `draft`, `needs-info`, `private-review`, and `private-hold`.
- Requests additionally require affirmative `ConsentToShare`; Donations require affirmative `PublicListingAllowed`; Reports require affirmative `PublicSummaryAllowed` and non-empty `PublicSummaryDraft`. Reports export the public draft only, never raw `Summary` or `SensitiveDetails`.
- Board-log output is aggregate-only: `Date`, `RecordType`, `Action`, and `Count`.
- Local fake coverage includes exact allowlists and denials, blank approvals, duplicate suppression, rows 101/150/final row and trailing empties, hostile HTML escaping, and dry-run no-write behavior.

## Controlled live credential-backed sync dry-run

A controlled live `--dry-run` completed with no filesystem writes and no Calendar creation. It read the full Sheet ranges and reported:

| Metric | Result |
| --- | --- |
| Rows read | Requests 12; Donations 7; Reports 23; Tasks 10; Inventory 8; CalendarLog 13; AuditLog 108 |
| Rows after row 100 | AuditLog 8 |
| Approved counts | needs 0; donations 0; reports 0; calendar 0; boardlog 11 |
| Requests rejections | `consent_not_affirmative` 4; `privacy_not_approved` 2; `status_not_public` 4 |
| Donations rejections | `privacy_not_approved` 5 |
| Reports rejections | `privacy_not_approved` 11; `public_summary_not_affirmative` 7; `status_not_public` 3 |
| Calendar rejections | `missing_calendar_event_id` 8 |
| Duplicate counts | Requests 1; Donations 1; Reports 1; Tasks 1; Inventory 1; AuditLog 0; CalendarLog 0 |
| Filesystem writes | 0 |

This is live read-only dry-run evidence. It proves no export files/pages were written by that run; it does not claim a live approved record was exported because all approved export counts were zero.

## Live header-only update and data-row immutability proof

The live header-only update completed for the appended fields listed above. No Sheet data rows changed:

| Tab | Data rows | Pre/post equality | SHA-256 |
| --- | ---: | --- | --- |
| Reports | 22 | equal | `2c5ee26fb233f92be8225a8ed0b9df53512976924955c91c7823517dc6367132` |
| Donations | 6 | equal | `474419f4863dccaa87c8a9ee733e84db78187e39ee46e77c0d3d3c38df0071e0` |

No data rows were deleted, backfilled, or otherwise changed by the header migration.

## Checker status

- The independent checker’s final `PASS` occurred **before** the schema append-order repair.
- The checker was not rerun after that repair; therefore that earlier checker pass does not attest to the post-repair report/state.
- Post-repair local schema parity was rerun and passed: `9 passed in 0.13s`.

## Scope/document blocker and worktree discipline

- After initial inspection, `docs/data/approved_board_log.json`, `docs/data/approved_donations.json`, `docs/data/approved_needs.json`, and `docs/data/approved_reports.json` were unexpected generated changes. They remain untouched and must be excluded from any CLEANUP-002 commit.
- Existing changed application paths are also outside this report-only scope: `scripts/non_profit_hermes_ops.py`, `scripts/sync_approved_safe_data.py`, and `scripts/telegram_intake_router.py`. New untracked CLEANUP-002 implementation/test paths are likewise present outside this report-only handoff.
- No docs/data restoration was performed, and no temporary comparison files remain. The docs diff was unchanged by the controlled dry-run/header update work.
- The current worktree is not clean; this is a documented scope blocker for committing. No commit or push was attempted.

## EVENT-004

**UNSTARTED.** No EVENT-004 implementation, plugin enablement/activation, gateway refresh/restart, Telegram registration, or live Telegram test was performed.
