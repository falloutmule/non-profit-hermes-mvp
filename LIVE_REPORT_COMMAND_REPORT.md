# LIVE_REPORT_COMMAND_REPORT.md

> **Historical report (2026-07-11, CLEANUP-001):** This report documents the initial `/report` wiring. The command is now **live and verified**. Plugin is gateway-active. Live draft/follow-up and scope-bridge were verified. The "pending" wording in the live Telegram section below is superseded — `/report` is active. See [PROJECT_STATUS.md](PROJECT_STATUS.md) for current status.

## Date
2026-07-09

## Goal
Wire Telegram `/report` as a live command using the same draft-first pattern as `/need` and `/donation`.

## What was done

### Backend (`scripts/non_profit_hermes_ops.py`)
- Added `Status`, `NextAction`, `Notes`, `LastUpdated` columns to Reports header (17→21 columns)
- Added `ensure_header()` to sync sheet headers before every report read/write
- Updated `add_report()` to populate Status=needs-info, NextAction=review, Notes, LastUpdated
- Added `update_report()` — full update-by-ReportID with before/after audit logging

### Router (`scripts/telegram_intake_router.py`)
- Replaced stub `route_report()` with draft-first implementation:
  - Accepts sloppy free text as summary/description
  - Auto-generates ReportID
  - Defaults to status=needs-info, privacy=private-review
  - Lists 8 missing fields: report_type, date, people_served_estimate, items_distributed, followups_needed, privacy_level, public_summary_allowed, next_action
- Added `route_report_followup()` with active draft tracking
- Added `get_active_report_id`, `set_active_report_id`, `clear_active_report_id`
- Added `report_row_by_id`, `open_report_drafts`, `resolve_report_followup_target`
- Wired report follow-up into `handle_message()` (checked before donation/need)
- Updated `_result_to_text()` to be command-aware ("Draft Report created" vs generic)

### Plugin
- Created `C:\Users\fallo\AppData\Local\hermes\plugins\non-profit-hermes-report\`
  - `plugin.yaml` (kind: standalone)
  - `__init__.py` (register /report, calls telegram_intake_router)
- Enabled via `hermes plugins enable non-profit-hermes-report`

## What was verified locally

### Test 1: Draft creation
```
/report pantry gave out socks and toilet paper
→ ok=True, status=needs-info, id=REP-E19BE9AC
→ privacy=private-review, backend=created
→ missing: report_type, date, people_served_estimate, items_distributed, followups_needed, privacy_level, public_summary_allowed, next_action
→ active draft pointer set
```

### Test 2: Follow-up without ReportID
```
report_type=pantry date=today people_served_estimate=unknown items_distributed="socks and toilet paper" followups_needed=none privacy_level=board-visible public_summary_allowed=yes status=ready next_action=review
→ ok=True, status=updated, id=REP-E19BE9AC (same row)
→ backend=updated
→ active draft pointer cleared (status=ready)
```

### Test 3: Audit + sync + export
- AuditLog: 2 entries (create + update), both result=success
- sync_approved_safe_data.py: ran successfully
- approved_reports.json: includes REP-E19BE9AC with board-visible fields only
- No sensitive/private details exported
- /daily: shows reports count

## What was verified in live Telegram

- Gateway recovered externally (PID 1868)
- Plugin enabled in Hermes registry
- Live Telegram test: pending (requires /report command to be available in bot registry after gateway recovery)

## What failed
Nothing.

## Current exact state
- Plugin: enabled, registered as `/report`
- Router: draft-first creation + follow-up works
- Backend: `add_report` + `update_report` with header sync works
- Audit: create + update entries confirmed
- Export: approved_reports.json has only safe fields

## Remaining blockers
None for `/report`. Do not wire `/task`, `/inventory`, or `/event` yet.

## Commit
(see git log for hash)