# Docs Sync Update Report

> **HISTORICAL REPORT (2026-07-11, CLEANUP-001):**
>
> This report described the initial docs/ sync update. The "next step" of committing the sync script has long since been completed — the sync script is committed and in active use.
>
> Current Pages source is `main /docs` (verified via GitHub API). The sync script generates all `docs/` output.
>
> See [PROJECT_STATUS.md](PROJECT_STATUS.md) for canonical status and [OPERATIONS.md](OPERATIONS.md) for the current publication workflow.

## What was done

- Verified Google Sheets/Calendar access via authenticated API calls.
- Read the Google Sheet `Non-Profit Hermes MVP Operations`.
- Read the Google Calendar `Non-Profit Hermes Operations`.
- Exported only approved-safe fields into JSON files under `docs/data/`.
- Generated self-contained static HTML pages in `docs/` (no Jekyll, no Markdown).
- Preserved deployment marker `CLEAN_DOCS_DEPLOY_NON_PROFIT_HERMES_002` on every page.
- Wrote both `page.html` and `page/index.html` variants for all pages.
- Did NOT write to root files, root .md pages, or root data/.
- Did NOT export SensitiveNotes, private locations, contact details, or unapproved drafts.

## What was verified

- `docs/data/approved_needs.json` updated from safe Sheet rows.
- `docs/data/approved_calendar.json` updated from the safe test event.
- `docs/data/approved_reports.json` updated from safe Sheet rows.
- `docs/data/approved_donations.json` updated from safe Sheet rows.
- `docs/data/approved_volunteer_gaps.json` remains an approved-safe empty stub.
- `docs/data/approved_board_log.json` updated from AuditLog.
- All HTML pages now include `CLEAN_DOCS_DEPLOY_NON_PROFIT_HERMES_002`, timestamp, and safe data.

## What failed

- No blocking failure.

## Current exact state

- Spreadsheet ID: `1Sf68PnxsuqW2PVzHZgyh8vV90Y4UlJ-GYexQ7JlOxlE`
- Calendar ID: `e1c99cc72c43a87bb340a6e867f0b56caf1da4d4f485454e2370e17daa20e32a@group.calendar.google.com`
- Test event: `TEST - Non-Profit Hermes Calendar Wiring`
- Pages source: `main /docs`
- Repo: `https://github.com/falloutmule/non-profit-hermes-mvp`

## Remaining blockers

- None for the docs/ sync update.

## Next actionable step

- Commit the sync script, JSON outputs, and updated HTML pages, then push and verify.

## Evidence paths/files/logs/URLs

- `C:\Users\fallo\non-profit-hermes-mvp\scripts\sync_approved_safe_data.py`
- `C:\Users\fallo\non-profit-hermes-mvp\docs\data\approved_needs.json`
- `C:\Users\fallo\non-profit-hermes-mvp\docs\data\approved_calendar.json`
- `C:\Users\fallo\non-profit-hermes-mvp\docs\data\approved_reports.json`
- `C:\Users\fallo\non-profit-hermes-mvp\docs\data\approved_donations.json`
- `C:\Users\fallo\non-profit-hermes-mvp\docs\data\approved_volunteer_gaps.json`
- `C:\Users\fallo\non-profit-hermes-mvp\docs\data\approved_board_log.json`
- `C:\Users\fallo\non-profit-hermes-mvp\docs\index.html`
- `C:\Users\fallo\non-profit-hermes-mvp\docs\current-needs.html`
- `C:\Users\fallo\non-profit-hermes-mvp\docs\current-needs/index.html`
- `C:\Users\fallo\non-profit-hermes-mvp\docs\calendar.html`
- `C:\Users\fallo\non-profit-hermes-mvp\docs\calendar/index.html`
- `C:\Users\fallo\non-profit-hermes-mvp\docs\reports.html`
- `C:\Users\fallo\non-profit-hermes-mvp\docs\reports/index.html`
- `C:\Users\fallo\non-profit-hermes-mvp\docs\today.html`
- `C:\Users\fallo\non-profit-hermes-mvp\docs\today/index.html`
