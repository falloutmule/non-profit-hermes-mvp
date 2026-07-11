# Operations — Non-Profit Hermes MVP

**Last updated:** 2026-07-11 13:48 MDT (CLEANUP-002 closeout)

## Daily operations and publication boundary

`/daily` is live for operations summaries. Its coupling to generation behavior remains the outstanding P0 concern.

**Publication is frozen until CLEANUP-003 separates `/daily` from generation.** Do not use `/daily` as authorization to create, commit, push, or publish an approved-safe snapshot. There is no automatic approval backfill.

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

`/event` creates CalendarLog drafts only. Calendar creation remains disabled in the live plugin. EVENT-004 is **unstarted and blocked**; it has not authorized live Calendar promotion, plugin activation, gateway refresh/restart, Telegram registration, or live Telegram testing.

Retained EVENT-003 evidence: draft `EVT-FC5611E9` was created and updated in CalendarLog row 13 with a blank `CalendarEventID`; the required read-only Calendar search returned zero matches. This historical draft-only verification does not authorize EVENT-004.

No live Google Calendar event has been created by the draft-first `/event` flow.
