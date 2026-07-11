# LIVE EVENT COMMAND REPORT — EVENT-003

## Scope and safety

EVENT-003 implements draft-first Telegram `/event` intake. The live plugin is locked to `allow_calendar_creation=False`; router and plugin do not create a Google Calendar event in this milestone.

## Local router verification — LOCAL FAKE-VERIFIED

- Sloppy free text is preserved exactly in both `EventTitle` and `Notes`.
- Structured drafts accept timezone-aware ISO timestamps with numeric offsets or trailing `Z`.
- Naive ISO timestamps are rejected as incomplete and are not guessed as UTC.
- Draft create/update uses `upsert_event_draft()` and keeps `CalendarEventID` blank.
- Active event state is source-scoped and preserves all existing active pointers and the `telegram:live -> telegram:6080816249` bridge.
- Explicit EventDraftID overrides the active pointer; multiple open drafts produce an ambiguity response.
- Cancelled/rejected drafts clear the event pointer.
- Existing report/task/inventory/donation/need follow-up routing is not intercepted.

Commands:

```text
python -m pytest tests/test_event_router.py -q
..............                                                           [100%]
14 passed in 0.23s

python -m pytest tests/test_event_draft_backend.py -q
.............                                                      [100%]
13 passed, 6 subtests passed in 0.13s

python -m pytest tests/test_event_calendar_privacy.py -q
........                                                            [100%]
8 passed, 5 subtests passed in 0.13s

python -m pytest -q
...................................                           [100%]
35 passed, 11 subtests passed in 0.23s

python -m py_compile scripts/telegram_intake_router.py tests/test_event_router.py C:/Users/fallo/AppData/Local/hermes/plugins/non-profit-hermes-event/__init__.py
(exit 0; no output)

git diff --check
(exit 0; no output)
```

## Fake Calendar promotion verification — LOCAL FAKE-VERIFIED

`tests/test_event_router.py` verifies explicit fake-enabled promotion and a repeated explicit promotion through the router. The retry returns the same existing `CalendarEventID` with `already_created`, while preserving exactly one fake Calendar insert, one CalendarLog row, and the same stored ID. This does not authorize or represent a live Calendar write.

## Plugin safety and invocation — LOCAL OFFLINE TEST-VERIFIED

External plugin path:

```text
C:\Users\fallo\AppData\Local\hermes\plugins\non-profit-hermes-event\
```

Files:

```text
__init__.py
plugin.yaml
```

The plugin registers `/event`, calls the repository router with `source_link="telegram:6080816249"` and explicit `allow_calendar_creation=False`, renders through `_result_to_text()`, and contains no direct Calendar backend call. An offline regression test imports the external plugin and invokes its actual `_event` handler while intercepting the router import with an in-memory fake. It proves the exact source link and disabled flag, and verifies the returned rendered response says `Draft Event created`, `Calendar: not created`, includes the EVENT-004-disabled notice, and has no line beginning `Event created`. Because the fake prevents the repository router and its dependencies from loading, this test cannot make a Google, Telegram, gateway, or network call. Separate router regressions exercise the actual renderer for both sloppy `needs-info` and structured `new` drafts. Plugin files exist on disk. Gateway activation was not tested and no gateway restart/kill/relaunch was performed.

## Live Telegram draft-only verification — NOT PERFORMED

No Telegram message was sent. No live command invocation or gateway-active status is claimed.

## Live Google Sheets evidence — NOT PERFORMED

No live Sheets call was made. Therefore there is no EVENT-003 live EventDraftID, row-count evidence, or create/update AuditLog ID.

## Live Google Calendar actions — NOT PERFORMED

No live Google Calendar read, write, promotion, edit, deletion, or duplicate check was performed. Calendar creation remains disabled in the plugin.

## Plugin and gateway status

- Prior independent checker: it passed the implementation and the then-current report, before the later activation-status claims were added. It did not pass or verify this newly updated report or its completion wording; no checker PASS is claimed here.
- Plugin enabled on disk: **yes**. `hermes plugins enable non-profit-hermes-event` completed, and `hermes plugins list --enabled` lists `non-profit-hermes-event` as enabled.
- Gateway-active: **unverified and pending a user-controlled gateway refresh**. Enabling the plugin does not activate it in the already-running gateway session.
- Exact activation blocker: the enable command reported `Takes effect on next session.` The gateway was not restarted, killed, or relaunched, as required. Consequently this current gateway session cannot provide live Telegram `/event` evidence.

## Remaining EVENT-004 work

EVENT-004 is a separate milestone and has not begun. Its remaining work is:

- Authorize one safe fake Calendar event.
- Perform controlled router promotion.
- Verify the exact same-row `CalendarEventID` update.
- Retry the promotion and verify that no duplicate event is created.
- Verify that the private event is excluded from public docs.
- Authorize one explicitly approved public-safe event or approved fixture.
- Verify the approved-safe Calendar export and `/daily`.
- Decide the final confirmation/plugin gate production policy.

## Completion status and next action

- Contract path: **Ready to commit under the concrete activation-blocker path; not yet complete**. Local router/renderer coverage and actual offline plugin `_event` invocation are verified. Gateway-active/live Telegram evidence remains unavailable until a user-controlled gateway refresh/new session.
- Commit/push and clean-working-tree confirmation remain pending post-report steps. This report does not claim they have occurred.
- No live Telegram command, Google Sheets read/write, Google Calendar action, Audit ID, test EventDraftID, or proof of no `EVT-*` Calendar event was produced in this gateway session.
- Next actions: commit and push the reviewed changes, confirm a clean working tree, then—after the user performs a controlled gateway refresh/new session—separately authorize and run the live draft-only Telegram `/event` verification. Capture the exact Telegram responses, test EventDraftID, create/update AuditLog IDs, same-row Sheets evidence, and proof that no `EVT-*` Calendar event was created.

## Evidence paths

```text
scripts/telegram_intake_router.py
tests/test_event_router.py
LIVE_EVENT_COMMAND_REPORT.md
C:\Users\fallo\AppData\Local\hermes\plugins\non-profit-hermes-event\__init__.py
C:\Users\fallo\AppData\Local\hermes\plugins\non-profit-hermes-event\plugin.yaml
```
