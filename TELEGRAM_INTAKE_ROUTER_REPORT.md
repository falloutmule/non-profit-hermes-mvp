# Telegram Intake Router Report

## What was done

- Inspected the existing Non-Profit Hermes skill:
  - `C:\Users\fallo\AppData\Local\hermes\skills\productivity\non-profit-hermes\SKILL.md`

- Inspected the repo:
  - `C:\Users\fallo\non-profit-hermes-mvp`

- Inspected the tested backend write module:
  - `scripts/non_profit_hermes_ops.py`

- Inspected the approved-safe docs sync script:
  - `scripts/sync_approved_safe_data.py`

- Inspected actual Hermes slash command behavior before modifying anything:
  - `hermes --help`
  - `hermes skills --help`
  - `hermes gateway status`
  - `hermes_cli/commands.py`
  - `hermes_cli/plugins.py`
  - Hermes docs for Telegram and slash commands

- Determined safest command path:
  - Use a repo-local router for simulated Telegram command intake.
  - Do not bypass `scripts/non_profit_hermes_ops.py`.
  - Use Hermes plugin slash-command support only for live `/daily`.
  - Do not wire live `/need`, `/donation`, `/report`, `/task`, `/inventory`, or `/event` yet.

- Created router:
  - `scripts/telegram_intake_router.py`

- Router supports:
  - `/need`
  - `/donation`
  - `/report`
  - `/task`
  - `/inventory`
  - `/event`
  - `/daily`

- Router maps commands to backend functions:
  - `/need` → `add_request`
  - `/donation` → `add_donation`
  - `/report` → `add_report`
  - `/task` → `add_task`
  - `/inventory` → `update_inventory`
  - `/event` → `create_calendar_event`
  - `/daily` → run sync and summarize approved-safe board state

- Added test mode:
  - `python scripts/telegram_intake_router.py --test`

- Added live `/daily` plugin files outside the repo in the active Hermes profile:
  - `C:\Users\fallo\AppData\Local\hermes\plugins\non-profit-hermes-daily\plugin.yaml`
  - `C:\Users\fallo\AppData\Local\hermes\plugins\non-profit-hermes-daily\__init__.py`

- Enabled only the `/daily` plugin:
  - `hermes plugins enable non-profit-hermes-daily`

## What was verified

- Router test command ran successfully:
  - `python scripts/telegram_intake_router.py --test`

- Simulated Telegram writes succeeded through the backend:
  - `/need` wrote `REQ-TG-TEST-001`
  - `/donation` wrote `DON-TG-TEST-001`
  - `/report` wrote `REP-TG-TEST-001`
  - `/task` wrote `TASK-TG-TEST-001`
  - `/inventory` wrote `INV-TG-TEST-001`
  - `/event` created Google Calendar event `5g0ch02a1imu8e7g9v0f5oljrs`
  - `/daily` produced a readable board-facing summary

- Required sync after router test writes succeeded:
  - `python scripts/sync_approved_safe_data.py`

- Sync output:
  - `approved_needs`: 4
  - `approved_calendar`: 4
  - `approved_reports`: 4
  - `approved_donations`: 4
  - `approved_volunteer_gaps`: 0
  - `approved_board_log`: 21
  - marker: `CLEAN_DOCS_DEPLOY_NON_PROFIT_HERMES_002`

- Direct Google Sheets verification succeeded:
  - Requests tab contains `REQ-TG-TEST-001`
  - Donations tab contains `DON-TG-TEST-001`
  - Reports tab contains `REP-TG-TEST-001`
  - Tasks tab contains `TASK-TG-TEST-001`
  - Inventory tab contains `INV-TG-TEST-001`
  - CalendarLog tab contains `CAL-TG-TEST-001`
  - AuditLog contains the Telegram router write/audit entries

- Direct Google Calendar verification succeeded:
  - Event ID: `5g0ch02a1imu8e7g9v0f5oljrs`
  - Event title: `CAL-TG-TEST-001 — Safe fake Telegram calendar event`
  - Status: `confirmed`

- AuditLog verified:
  - `AUDIT-1030B79A` → Requests/REQ-TG-TEST-001
  - `AUDIT-D06548FD` → Donations/DON-TG-TEST-001
  - `AUDIT-051B5337` → Reports/REP-TG-TEST-001
  - `AUDIT-373FBD8C` → Tasks/TASK-TG-TEST-001
  - `AUDIT-EBB66D2D` → Inventory/INV-TG-TEST-001
  - `AUDIT-12AC2E01` → Calendar/5g0ch02a1imu8e7g9v0f5oljrs
  - `AUDIT-F0A134FB` → held sensitive test message
  - `AUDIT-95D7FF72` → missing field test message

- Privacy behavior verified:
  - Sensitive test input was held, not written to public-safe records.
  - Missing-field test returned `needs_more_info` and did not invent details.
  - Unknown optional fields are marked `unknown`.
  - Privacy classification marks normal safe tests as `board-visible`.
  - Sensitive terms trigger `private-hold`.

- Docs export privacy check verified:
  - grep across docs HTML/JSON for sensitive terms returned no matches.
  - No `SensitiveNotes` exported.
  - No medical, addiction, legal, camp, family crisis, private-location, phone, or address-like data exported.

- `/daily` plugin handler verified directly after plugin discovery:
  - `daily_registered= True`
  - Handler returned the board-safe daily summary.

## What failed

- Live gateway restart failed from inside the running gateway process.

Exact failure:

```text
Blocked: cannot restart or stop the gateway from inside the gateway process. The gateway would kill this command before it could complete (SIGTERM propagates to child processes). Run `hermes gateway restart` from a separate shell outside the running gateway.
```

This means live `/daily` is installed and enabled, but the active Telegram gateway process must be restarted externally before Telegram will load the new plugin command.

## Current exact state

- Repo router exists:
  - `scripts/telegram_intake_router.py`

- Simulated Telegram intake is working and verified.

- Google Sheets state after sync:
  - Requests rows: 5, includes `REQ-TG-TEST-001`
  - Donations rows: 5, includes `DON-TG-TEST-001`
  - Reports rows: 5, includes `REP-TG-TEST-001`
  - Tasks rows: 5, includes `TASK-TG-TEST-001`
  - Inventory rows: 5, includes `INV-TG-TEST-001`
  - CalendarLog rows: 5, includes `CAL-TG-TEST-001`
  - AuditLog rows: 22 direct / 21 approved-safe exported board log entries

- Google Calendar state:
  - `CAL-TG-TEST-001 — Safe fake Telegram calendar event`
  - Event ID: `5g0ch02a1imu8e7g9v0f5oljrs`
  - Status: `confirmed`

- Docs state:
  - `docs/data/approved_needs.json` contains `REQ-TG-TEST-001`
  - `docs/data/approved_donations.json` contains `DON-TG-TEST-001`
  - `docs/data/approved_reports.json` contains `REP-TG-TEST-001`
  - `docs/data/approved_calendar.json` contains `CAL-TG-TEST-001`
  - `docs/data/approved_board_log.json` contains Telegram router audit entries

- Live `/daily` plugin state:
  - Plugin created.
  - Plugin enabled.
  - Plugin command handler verified directly.
  - Gateway restart is still required from outside the gateway process.

## Remaining blockers

- External gateway restart is required to activate live `/daily` in Telegram.

Run from a separate shell outside Telegram/gateway:

```bash
hermes gateway restart
```

Then test in Telegram:

```text
/daily
```

## Next actionable step

- Restart the Hermes gateway from an external shell.
- Verify `/daily` in Telegram.
- Only after `/daily` is verified live, wire one additional command at a time, starting with `/need` or `/donation`.

## Evidence paths/files/URLs

- Router:
  - `C:\Users\fallo\non-profit-hermes-mvp\scripts\telegram_intake_router.py`

- Backend write module:
  - `C:\Users\fallo\non-profit-hermes-mvp\scripts\non_profit_hermes_ops.py`

- Sync script:
  - `C:\Users\fallo\non-profit-hermes-mvp\scripts\sync_approved_safe_data.py`

- Report:
  - `C:\Users\fallo\non-profit-hermes-mvp\TELEGRAM_INTAKE_ROUTER_REPORT.md`

- Live `/daily` plugin:
  - `C:\Users\fallo\AppData\Local\hermes\plugins\non-profit-hermes-daily\plugin.yaml`
  - `C:\Users\fallo\AppData\Local\hermes\plugins\non-profit-hermes-daily\__init__.py`

- Approved-safe exports:
  - `C:\Users\fallo\non-profit-hermes-mvp\docs\data\approved_needs.json`
  - `C:\Users\fallo\non-profit-hermes-mvp\docs\data\approved_donations.json`
  - `C:\Users\fallo\non-profit-hermes-mvp\docs\data\approved_reports.json`
  - `C:\Users\fallo\non-profit-hermes-mvp\docs\data\approved_calendar.json`
  - `C:\Users\fallo\non-profit-hermes-mvp\docs\data\approved_board_log.json`

- GitHub Pages:
  - `https://falloutmule.github.io/non-profit-hermes-mvp/`
  - `https://falloutmule.github.io/non-profit-hermes-mvp/deployment-proof/`
