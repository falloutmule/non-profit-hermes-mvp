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

Preserve all 12 existing occurrence IDs and rename their display name Saturday Feed. Categories: Pantry/PANTRY5; Harm Reduction / First Aid / Hygiene/SUPPLIES4; Meal/MEAL1. Total10 derived; independent standby. Completion reporting off, America/Denver Saturdays15:45–17:00, 302 South Ave, Grand Junction. Adopt recurrence through the authenticated series API, preserving IDs/status. Existing `HermesVolunteerBoard-PantryDrafts` materializes future drafts from the stored rule, not an independent event calendar.

`SYSTEM_INTEGRATION_PASS` is separate from the real-use wording/campaign review. `real_use_review_complete` remains false until the approved campaign and live consent/public wording are compared. No automated Twilio modification. Saturday Pantry stays draft; publication/invitations require explicit user authorization even after the wording gate passes.

## Verification and rollback

Use isolated adapter/Board fixtures for writes and SMS. Live checks are reads, legitimate recurrence adoption, inspection projection and menu configuration. No fake Google records, real SMS, invitations or publication.

Before a Board schema upgrade take a verified online backup with the old runtime. Rollback across schema versions restores the matching pre-upgrade database with the old tested application; never run old code against an upgraded database. After accepting new writes, preserve the latest authoritative state before any rollback.

Historical evidence records earlier connector/menu/OAuth states; this guide supersedes those operating procedures.

## Saturday Feed categories (current model)

The preserved series ID is `saturday-pantry`; its display name is Saturday Feed. Preserve occurrence IDs and dated slugs. Pantry uses PANTRY, five places; Harm Reduction / First Aid / Hygiene uses SUPPLIES, four places; Meal uses MEAL, one place. All have separate standby queues. Total capacity is derived, never edited directly. DONE is disabled for this series.

Use `action="categories"` through the existing `--request` stdin adapter. Supply the complete category definition list with key,name,capacity,standbyEnabled,active,sortOrder. `scope="one"` requires eventId; `scope="future"` requires seriesId and effectiveFrom date. Read current categories first and preserve fields the user did not request changing. Do not rename stable keys to change display names. The Board validates commitments and protects overrides. For an ambiguous change ask this occurrence versus this and future occurrences. A future change preserves prior per-date overrides.

Examples: “Make Pantry six places next Saturday”; “Make Meal two places for future Saturdays”; “Move this Saturday to 4 PM”. Never require the user to type JSON or look up IDs. Confirm the changed category/date and old → new value. Event times still use the event update/series schedule paths. `/board` and `/daily` show separate category needs and reservations; drafts are not open for signup.

Volunteers who already opted in text PANTRY, SUPPLIES or MEAL, choose an offered Saturday by number and reply YES. Full categories require explicit YES for standby. Category keywords do not grant consent. Date choices expire after30minutes; NEXT pages choices. Signup closes at event start. One active assignment per occurrence: explain DROP and rejoin rather than switching categories automatically. Old dated slugs lead to category choice. No cross-category standby, no attendance, and no general SMS reporting.

Publication/invitations remain held. The category implementation changes neither the real-use review gate nor Twilio settings. A configured webhook is not proof of fresh real-phone delivery.
