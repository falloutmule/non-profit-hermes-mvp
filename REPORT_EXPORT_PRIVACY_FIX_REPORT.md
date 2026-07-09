# REPORT_EXPORT_PRIVACY_FIX_REPORT.md

## Date
2026-07-09

## Problem
`docs/data/approved_reports.json` was exporting 8 private-review report rows, violating the privacy gate. The `safe_reports()` function in the sync script had zero privacy filtering — it exported every report row regardless of PrivacyLevel, Status, or public_summary_allowed flag.

Leaked IDs: REP-A4545CCC, REP-4F971ECC, REP-BD9FA1E6, REP-E32E60B8, REP-2AA392B2, REP-4E3357DC, REP-33758116, REP-2287A951

## Fix applied

### 1. `safe_reports()` in sync_approved_safe_data.py
Added three exclusion gates before appending:
- **PrivacyLevel**: skip private-review, private-hold (only allow board-visible, public-safe, board-visible-test)
- **Status**: skip needs-info, draft
- **public_summary_allowed**: skip if explicitly no/false/0

### 2. `safe_board_log()` audit filtering
Added `visible_report_ids` parameter. Audit entries with `TargetItem` matching `Reports/<id>` are now filtered out when the report ID is not in the safe/visible set. Previously only `Requests/` entries were filtered.

### 3. `_result_to_text()` in telegram_intake_router.py
Replaced hardcoded `/need` example with command-aware `_example_for_command()` helper. The missing-summary reply now shows:
- "Need more info to create this Report." (not "request")
- `/report type=pantry summary=...` example (not `/need`)

### 4. Plugin argument forwarding verified correct
`non-profit-hermes-report/__init__.py` line 13: `"/report " + args.strip()` — correctly preserves full text including sloppy free-text descriptions.

## Verification

### Privacy export
- `approved_reports.json`: 6 board-visible-only reports, zero private-review
- `docs/` grep: zero hits for all 8 leaked IDs
- `docs/` grep: zero hits for "private-hold" or "private-review"
- Board-visible REP-E19BE9AC still exported correctly

### Reply fix
- `/report pantry gave out socks and toilet paper` → draft created, report-type example
- `/report` (empty) → "Need more info to create this Report. Missing: summary." with `/report` example

### Daily summary
- Still runs, shows 6 approved reports, website-links-dedup-003 intact
