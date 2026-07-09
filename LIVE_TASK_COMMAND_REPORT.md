# LIVE_TASK_COMMAND_REPORT.md

## Date
2026-07-09

## Goal
Wire Telegram `/task` as a live command using the draft-first pattern proven for `/report`.

## What was done

### Backend (`non_profit_hermes_ops.py`)
- Added `SourceMessageLink` and `Notes` to Tasks header (16→18 columns)
- Added `ensure_header(svc, "Tasks")` to `add_task()` and `update_task()`
- Added `update_task()` — full update-by-TaskID with before/after audit logging

### Router (`telegram_intake_router.py`)
- Replaced stub `route_task()` with draft-first implementation:
  - Accepts sloppy free text as title/description
  - Auto-generates TaskID
  - Defaults to status=needs-info
  - Lists 5 missing fields: assigned_to, due_date, priority, privacy_level, next_action
- Added task active draft tracking (get/set/clear_active_task_id)
- Added `task_row_by_id`, `open_task_drafts`, `resolve_task_followup_target`
- Added `route_task_followup()` with command-specific field detection
- Wired task follow-up into `handle_message()` (between report and donation)
- Updated `_example_for_command()` with task example

### Follow-up chain fix
Each follow-up handler now checks for command-specific fields before intercepting:
- Report: report_type, people_served_estimate, items_distributed, etc.
- Task: assigned_to, due_date, priority
- Returns `None` (falls through) if no relevant fields and no active draft
- Prevents wrong-command interception

### Plugin
- Created `non-profit-hermes-task` plugin (plugin.yaml + __init__.py)
- `source_link="telegram:6080816249"` (compatible with source_scope bridge)
- Enabled via `hermes plugins enable`

## Verification

### Local test
```
/task call volunteer about socks
→ ok=True, status=needs-info, id=TASK-6DA4B4EE, 5 missing fields

assigned_to=unknown due_date=unknown priority=normal privacy_level=internal status=ready
→ ok=True, status=updated, id=TASK-6DA4B4EE (same row), active pointer cleared
```

### Cross-contamination check
- Report create + follow-up still works (not intercepted by task handler)
- No wrong-command mismatches

### Daily + sync
- sync_approved_safe_data.py runs clean
- /daily still functional with website-links-dedup-003 marker

### Live Telegram
- Plugin enabled, awaits gateway session for `/task` command to activate
- Builds on same source_scope bridge as /report

## Notes
- Tasks are internal-only (not exported to docs/ publicly)
- Follow-up clears active pointer on ready/done/complete status
- Uses existing Tasks sheet tab and AuditLog
