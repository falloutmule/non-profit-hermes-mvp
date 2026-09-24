# Unified nonprofit operating workflow

Hermes profile `nonprofit-v1` is the operator; `@HnonProfitBOT` is the organization interface.

## Sources of truth

- Volunteer Board: all new events, recurrence, capacity, staffing, standby, cancellations, completion and SMS state.
- Existing private Google workbook: needs, donations, tasks, inventory, reports and established approval records.
- Member Operations: generated one-way inspection of both sources, never an independently editable signup system.
- Google Calendar: published Board event view, using stable Board identity. Drafts remain off Calendar.
- Docs/Drive: real documents, not another database. No dummy document is needed.

## Telegram

Menu: `/daily /need /donation /report /task /inventory /event /board /new /usage /status /model /stop`.

`/daily` reads organization counts, safely visible inventory warnings and Board staffing. `/need`, `/donation`, `/report`, `/task` and `/inventory` retain the installed nonprofit package workflows. Bare commands show help without creating empty records.

`/event` manages what, when and where. New events default to draft, staffing off, standby off and completion reporting off. Natural-language requests use the same bounded adapter as the command. Recurring schedule edits require one occurrence versus future occurrences to be explicit. `/event show 1` inspects the event; `/event update 1 {"capacity":6}` is an explicit single-occurrence edit. Creation accepts structured JSON through the adapter, while the Hermes skill handles conversational clarification.

`/board` is read-first: confirmed count, openings, standby, cancellations and pending offers. `/board show 1` reads staffing. Event changes belong to `/event`. Organizer overrides use only existing bounded Board API operations with explicit authorization, no arbitrary state/SQL editor.

## SMS completion

Reportable events set `completionReportRequired=true` and an organizer-written `completionStatement`. An eligible confirmed volunteer sends `DONE` or `DONE <event keyword>`. Completion closes the whole assignment/event upon the first valid report. Ambiguity requires a keyword. It is not attendance or individual scoring. Normal Pantry shifts require no DONE. No arbitrary message body is retained or interpreted by AI.

## Runtime

Source dispatch: `scripts/nonprofit_workflow.py`. Adapter: `scripts/volunteer_board_operator.py`. The dedicated profile plugin loads them at invocation. `runtime_plugins/nonprofit-v1-board-overlay/commands.py` and `SKILL.md` are the reproducible deployed overlay.

Profile: `C:\Users\fallo\AppData\Local\hermes\profiles\nonprofit-v1`.
Task: `Hermes_Gateway_nonprofit_v1`, dedicated listener 8643. Never stop the shared/main Hermes gateway. Stop this task, verify and stop only its remaining dedicated gateway child if necessary, then start this task. Bootstrap verifies registry and reapplies the exact bot menu 15 seconds after startup. Profile menu priority mirrors the same 13 commands.

Board credentials remain in protected `private/configuration/volunteer-board.json` with `base_url`, `admin_token`, `real_use_review_complete`. Loopback and no redirects are enforced; credentials never enter prompts. The canonical Google OAuth file is `C:\Users\fallo\AppData\Local\hermes\google_token.json`; profile aliases resolve to it. Refresh atomically updates that canonical file, retaining aliases.

## Human inspection and audit

See `MEMBER_OPERATIONS_PROJECTION.md`. Task `HermesNonProfit-MemberProjection` processes the transactional Board outbox every minute; five-minute reconciliation repairs drift and refreshes private Google source views. Success is acknowledged only after Sheets and Calendar succeed. Google failure cannot roll back Board changes. The workbook shows snapshot age and pending status.

Generated tabs: Overview, Events, Staffing, Needs, Tasks, Inventory, Donations Summary, Reports, Activity, Sync Status. The file starts owner-only. No sharing is broadened. Unclassified Tasks/donation details remain withheld; aggregate counts remain visible. Review intended records and Google permissions before sharing with members. Hidden columns are never a privacy boundary.

No phone numbers, consent/STOP state, Twilio IDs, private notes or SMS bodies are projected. Names are used where available; otherwise stable Volunteer #IDs. Activity mirrors sanitized Board audit and only safely visible existing Google record references.

## Pantry and release gate

Preserve all 12 existing Pantry dates. Capacity 6, staffing/standby on, completion reporting off, America/Denver Saturdays 15:45–17:00, 302 South Ave, Grand Junction. Adopt recurrence through the authenticated series API, preserving IDs/status. Existing `HermesVolunteerBoard-PantryDrafts` materializes future drafts from the stored rule, not an independent event calendar.

`SYSTEM_INTEGRATION_PASS` is separate from the real-use wording/campaign review. `real_use_review_complete` remains false until the approved campaign and live consent/public wording are compared. No automated Twilio modification. Saturday Pantry stays draft; publication/invitations require explicit user authorization even after the wording gate passes.

## Verification and rollback

Use isolated adapter/Board fixtures for writes and SMS. Live checks are reads, legitimate recurrence adoption, inspection projection and menu configuration. No fake Google records, real SMS, invitations or publication.

Before a Board schema upgrade take a verified online backup with the old runtime. Rollback across schema versions restores the matching pre-upgrade database with the old tested application; never run old code against an upgraded database. After accepting new writes, preserve the latest authoritative state before any rollback.

Historical evidence records earlier connector/menu/OAuth states; this guide supersedes those operating procedures.
