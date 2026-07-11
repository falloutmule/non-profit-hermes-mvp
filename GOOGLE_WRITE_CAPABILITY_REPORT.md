# Google Write Capability Report

> **HISTORICAL REPORT — Superseded by EVENT-001 (2026-07-11, CLEANUP-001):**
>
> This report describes the initial write-capability proof and the **pre-EVENT-001 calendar export policy**, which stated that all non-cancelled Calendar events are publicly exported. That policy was **replaced by EVENT-001** with CalendarLog-based approval gating. The current calendar publication policy requires a two-source join (CalendarLog approval + live Calendar ID existence check) and never exports raw Google Calendar event content.
>
> The test records described here (`REQ/DON/REP/TASK/INV/CAL-WRITE-TEST-001`) remain in the Sheet as historical artifacts.
>
> See [EVENT_CALENDAR_PRIVACY_REPORT.md](EVENT_CALENDAR_PRIVACY_REPORT.md) for the current calendar gate and [PROJECT_STATUS.md](PROJECT_STATUS.md) for canonical status.

## What was done

1. Created `scripts/non_profit_hermes_ops.py` — a backend module with 7 write operations:
   - `add_request` — writes to Requests tab
   - `add_donation` — writes to Donations tab
   - `add_report` — writes to Reports tab
   - `add_task` — writes to Tasks tab
   - `update_inventory` — writes to Inventory tab
   - `create_calendar_event` — creates real Google Calendar event + writes to CalendarLog tab
   - `write_audit_log` — writes to AuditLog tab (called by every other operation)

2. Ran `--test-write` CLI mode which created 6 safe fake test records:
   - **Request**: REQ-WRITE-TEST-001 → Requests tab
   - **Donation**: DON-WRITE-TEST-001 → Donations tab
   - **Report**: REP-WRITE-TEST-001 → Reports tab
   - **Task**: TASK-WRITE-TEST-001 → Tasks tab
   - **Inventory**: INV-WRITE-TEST-001 → Inventory tab
   - **Calendar event**: `9n5fjtt1c2jo82po3cosurvvds` → CalendarLog tab + Google Calendar

3. Ran `scripts/sync_approved_safe_data.py` to refresh the docs/ site with the new records.

4. Updated `scripts/sync_approved_safe_data.py` — `safe_calendar_export` now exports all non-cancelled calendar events (not just the single `TEST_EVENT_TITLE`), enabling proper sync of operational and write-test events.

## What was verified

- **Requests tab**: Contains REQ-WRITE-TEST-001 row (verified via sync output: 3 needs rows)
- **Donations tab**: Contains DON-WRITE-TEST-001 row (verified via sync output: 3 donation rows)
- **Reports tab**: Contains REP-WRITE-TEST-001 row (verified via sync output: 3 report rows)
- **Tasks tab**: Contains TASK-WRITE-TEST-001 row (written by test write; not exported to public docs/)
- **Inventory tab**: Contains INV-WRITE-TEST-001 row (written by test write; not exported to public docs/)
- **CalendarLog tab**: Contains CAL-WRITE-TEST-001 calendar event entry
- **Google Calendar**: Contains the CAL-WRITE-TEST-001 event (`9n5fjtt1c2jo82po3cosurvvds`, confirmed)
- **AuditLog tab**: Contains 6 new audit entries (one per operation) — verified in `approved_board_log.json`:
  - AUDIT-C3C64284 → Requests/REQ-WRITE-TEST-001
  - AUDIT-6789FF7A → Donations/DON-WRITE-TEST-001
  - AUDIT-A99496FB → Reports/REP-WRITE-TEST-001
  - AUDIT-D7953A2C → Tasks/TASK-WRITE-TEST-001
  - AUDIT-BCFB7BC3 → Inventory/INV-WRITE-TEST-001
  - AUDIT-4FA19B3A → Calendar/9n5fjtt1c2jo82po3cosurvvds
- **docs/data/approved_needs.json**: Contains REQ-WRITE-TEST-001
- **docs/data/approved_reports.json**: Contains REP-WRITE-TEST-001
- **docs/data/approved_calendar.json**: Contains 3 events (original test + 2 write-test events)
- **docs/data/approved_board_log.json**: Contains 13 entries (7 existing + 6 new)
- **Sensitive data check**: grep for SensitiveNotes, private location, phone, addiction, medical, legal, camp, family crisis → 0 matches in all docs/ HTML pages
- **Deployment marker**: `CLEAN_DOCS_DEPLOY_NON_PROFIT_HERMES_002` present on all pages
- **approved-safe sync verified**: Present on index.html
- **No SensitiveNotes exported**: Only safe fields (PrivacyLevel, LocationPublicSafe) included; SensitiveDetails field is empty with value `""`
- **No private contact/location data exported**: DonorName, DonorContact, LocationPrivate, PersonOrGroup, ContactMethod fields are all stripped by the sync script's safe-filtering functions

## What failed

Nothing. All 6 test writes succeeded. The sync script picked up all new records. Calendar events exported correctly with proper type classification.

## Current exact state

- **Repo state**: Main branch, up to date with origin/main. Changes staged for commit.
- **Sheets/Calendar write capability**: **proven working** via `non_profit_hermes_ops.py`
- **Sync from Sheets to docs/**: **proven working** via `sync_approved_safe_data.py`
- **Test records in Sheet**: REQ-WRITE-TEST-001, DON-WRITE-TEST-001, REP-WRITE-TEST-001, TASK-WRITE-TEST-001, INV-WRITE-TEST-001, Calendar event `9n5fjtt1c2jo82po3cosurvvds`
- **AuditLog entries**: 13 total (6 from latest test-write)
- **Spreadsheet ID**: `1Sf68PnxsuqW2PVzHZgyh8vV90Y4UlJ-GYexQ7JlOxlE`
- **Calendar ID**: `e1c99cc72c43a87bb340a6e867f0b56caf1da4d4f485454e2370e17daa20e32a@group.calendar.google.com`

## Remaining blockers

None for write capability. All 7 operations write correctly to their targets.

## Next actionable step

Wire Telegram commands (`/need`, `/donation`, `/daily`, etc.) to call these backend operations from `non_profit_hermes_ops.py`.

## Evidence paths/files/URLs

- `scripts/non_profit_hermes_ops.py` — backend operations module (583 lines, supports both programmatic and CLI use)
- `scripts/sync_approved_safe_data.py` — updated to export all calendar events
- `docs/data/approved_needs.json` — contains REQ-WRITE-TEST-001
- `docs/data/approved_reports.json` — contains REP-WRITE-TEST-001
- `docs/data/approved_calendar.json` — contains CAL-WRITE-TEST-001 events
- `docs/data/approved_board_log.json` — 6 new audit entries for write operations
- `docs/index.html` — homepage with approved-safe sync verified, deployment marker
- `docs/current-needs.html` — shows deployment marker
- `docs/deployment-proof.html` — shows deployment marker with record counts
- `docs/data/approved_donations.json` — contains DON-WRITE-TEST-001
- Google Sheet: `Non-Profit Hermes MVP Operations` (ID: `1Sf68PnxsuqW2PVzHZgyh8vV90Y4UlJ-GYexQ7JlOxlE`)
- Google Calendar: `Non-Profit Hermes Operations` (event: `9n5fjtt1c2jo82po3cosurvvds`)
