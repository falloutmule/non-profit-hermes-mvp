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

The plugin registers `/event`, calls the repository router with `source_link="telegram:6080816249"` and explicit `allow_calendar_creation=False`, renders through `_result_to_text()`, and contains no direct Calendar backend call. An offline regression test imports the external plugin and invokes its actual `_event` handler while intercepting the router import with an in-memory fake. It proves the exact source link and disabled flag, and verifies the returned rendered response says `Draft Event created`, `Calendar: not created`, includes the EVENT-004-disabled notice, and has no line beginning `Event created`. Because the fake prevents the repository router and its dependencies from loading, this test cannot make a Google, Telegram, gateway, or network call. Separate router regressions exercise the actual renderer for both sloppy `needs-info` and structured `new` drafts. Plugin files exist on disk. Subsequent controlled live verification confirmed that the running gateway loaded the command.

## Live Telegram draft-only verification — LIVE VERIFIED

The live Telegram `/event` create and same-session plain-text follow-up both succeeded through the active gateway. The create produced `EventDraftID EVT-FC5611E9`. The follow-up response reported the draft as cancelled, approval rejected, and Calendar not created. The live source scope was `telegram:6080816249`.

## Live Google Sheets, audit, and state evidence — LIVE VERIFIED

- A live Sheets query found exactly one matching `CalendarLog` row, at row 13.
- `EventDraftID`: `EVT-FC5611E9`
- `EventTitle`: `Safe fake EVENT-003 Telegram draft`
- `EventType`: `telegram-test`
- `Status`: `cancelled`
- `ApprovalStatus`: `rejected`
- `SourceMessageLink`: `telegram:6080816249`
- `Notes`: `EVENT-003 TEST RECORD - follow-up verified`
- `CalendarEventID`: blank
- Create audit entry: `AUDIT-D2849AD9`
- Update audit entry: `AUDIT-580A8E71`
- Post-follow-up state: `active_event_id` was cleared, while the existing `active_need_request_id` was preserved.

## Live Google Calendar evidence — READ-ONLY VERIFIED; ZERO EVENTS

A required read-only Google Calendar search returned 0 matching events. No Calendar write, promotion, edit, cancellation, or deletion occurred. The draft's `CalendarEventID` remains blank, and Calendar creation remains disabled in the plugin. The zero-event result is evidence that this controlled EVENT-003 draft-only flow did not create a Calendar event; it is not a claim that Calendar promotion was exercised.

## Plugin and gateway status

- Plugin enabled on disk: **yes**. `hermes plugins enable non-profit-hermes-event` completed, and `hermes plugins list --enabled` lists `non-profit-hermes-event` as enabled.
- Gateway-active: **verified**. The running gateway handled the live Telegram create and follow-up invocations.

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

- EVENT-003 live verification/evidence phase: **Complete**. Local router/renderer coverage, actual offline plugin `_event` invocation, gateway-active Telegram create/follow-up, the single matching Sheets row, both audit records, and source-scoped state cleanup are verified. This report is ready for an evidence-only commit.
- Full EVENT-003 completion remains pending the evidence-only commit, push, and clean-working-tree confirmation. This report does not claim they have occurred.
- Calendar boundary: **no Calendar write or promotion occurred**. Only the required read-only Calendar search was performed, and it returned 0 matching events; `CalendarEventID` is blank.
- Next action: review this evidence update, then commit and push separately when authorized. EVENT-004 remains separate and unchanged below.

## Evidence paths

```text
scripts/telegram_intake_router.py
tests/test_event_router.py
LIVE_EVENT_COMMAND_REPORT.md
C:\Users\fallo\AppData\Local\hermes\plugins\non-profit-hermes-event\__init__.py
C:\Users\fallo\AppData\Local\hermes\plugins\non-profit-hermes-event\plugin.yaml
```
