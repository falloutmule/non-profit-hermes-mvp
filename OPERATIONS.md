# Operations — Non-Profit Hermes MVP

**Last updated:** 2026-07-12 (EVENT-004 post-capture documentation reconciliation; see `EVENT_004_LIVE_CALENDAR_PROMOTION_REPORT.md`)

## Daily operations and publication boundary

`/daily` is live for operations summaries. CLEANUP-003 is complete and keeps it in read-only in-memory state; it does not generate or mutate publication output.

**Publication remains frozen.** Do not use `/daily` as authorization to create, commit, push, or publish an approved-safe snapshot. There is no automatic approval backfill.

The controlled CLEANUP-002 `--dry-run` found zero approved public needs, donations, and reports in the observed live data. Four generated JSON files were inspected and restored because no public snapshot publication was authorized.

## Explicit export inspection

Use the explicit sync command for local generation or inspection:

```bash
# Inspect live source data without filesystem writes
python scripts/sync_approved_safe_data.py --dry-run

# Generate a local approved-safe snapshot only when separately authorized
python scripts/sync_approved_safe_data.py
```

The dry-run reads full Sheet ranges, including rows after 100, and reports acceptance/rejection and duplicate evidence. It does not create Calendar events or write public files.

## Intake commands

All write commands use draft-first intake:

| Command | Creates | Default status | Default privacy |
|---|---|---|---|
| `/need <text>` | Requests row | needs-info | private-review |
| `/donation <text>` | Donations row | needs-info | private-review |
| `/report <text>` | Reports row | needs-info | private-review |
| `/task <text>` | Tasks row | needs-info | internal |
| `/inventory <text>` | Inventory row (upsert) | needs-info | internal |
| `/event <text>` | CalendarLog draft | needs-info | private-review |

Approved-safe exports are deny-by-default: requests require `ConsentToShare`, donations require `PublicListingAllowed`, and reports require `PublicSummaryAllowed` plus `PublicSummaryDraft`; all also require approved privacy and an allowed public status. Board logs are aggregate-only, and generated public HTML escapes user-controlled values.

## Google Sheets maintenance

CLEANUP-002 resolved the former row-100 read limit, canonical-schema divergence, and export deduplication gap. Header additions were append-only and preserved existing Reports and Donations data rows.

Historical test records remain data records. Do not delete, backfill, approve, or publish them without explicit authorization.

## Event operations

`/event` remains draft-first. The authoritative final EVENT-004 evidence JSON supports one explicitly renewed-authorized, synthetic promotion: draft `EVT-A31A0CF8` mapped to Calendar event `cpq3e1oivn4ajb4t8ktemjuj0g` on CalendarLog row 14, with final one-event/13-row counts, authorization absent, `private-review`, `PublicCalendarAllowed=no`, and approved-calendar exclusion. A direct installed-plugin retry observed during the execution session returned `already_created`; that retry observation is not contained in the JSON, while offline tests independently cover idempotence.

This exception does **not** enable general Calendar promotion. For every future promotion, require separate per-event human authorization; run preflight/guard checks; create only the named private-by-default draft; consume authorization immediately before the first external attempt (so it remains non-reusable after a failure); write the returned ID to the same row; and verify retry idempotence and privacy exclusion. Do not treat `/daily`, offline tests, or direct plugin invocation as promotion authority.

A controlled local `/daily` CLI proof observed during the execution session passed with zero writes; it left docs, working-tree status, and absent token state unchanged. Direct invocation of the installed daily gateway plugin was also observed to pass with an in-memory marker and zero writes. These execution-session observations are not contained in the authoritative final evidence JSON, which records final counts, hashes, and state. Neither is a human-originated Telegram-delivered message, so neither proves Telegram transport or user-command delivery.

Initial plugin-routing and sensitive-description-hold failures were contained and repaired before the successful EVENT-004 insertion. During the controlled evidence execution, no public snapshot, gateway restart, Telegram registration, deletion, SNC action, commit, staging, push, or unrelated live mutation was performed. The implementation was subsequently committed and pushed as historical commit `fb2911c8e4cdc0c2c4bcf5a67fcd948db74cf174` (`feat: add controlled event promotion authorization`); local/origin/GitHub `main` matched immediately after that push, not as a standing status claim. The documentation/evidence commit remains pending. Review and separately authorize any documentation/evidence commit, gateway work, or future live promotion. See `EVENT_004_LIVE_CALENDAR_PROMOTION_REPORT.md` for evidence and audit IDs.

Retained EVENT-003 evidence: draft `EVT-FC5611E9` was created and updated in CalendarLog row 13 with a blank `CalendarEventID`; the required read-only Calendar search returned zero matches. This historical draft-only verification does not authorize future promotions.
