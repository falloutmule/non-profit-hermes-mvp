# EVENT-004 Live Calendar Promotion Report

## Goal

Document the controlled EVENT-004 promotion of one explicitly authorized, synthetic CalendarLog draft into the configured Google Calendar. This report records the evidence only; it does not grant continuing Calendar, publication, or message-delivery authority.

## Starting commit

The execution began from repository commit `871131e26275148260c26a7366ff4fd43e57144d`.

## Authorization received

A renewed, explicit user authorization was received for this single controlled live promotion. The authorization was consumed immediately before the first external promotion attempt, so it was non-reusable even if that attempt failed. It did not authorize other drafts, public publication, deletion, gateway restart, Telegram registration, or any unrelated live mutation.

## Authorized event fields

| Field | Authorized/observed value |
|---|---|
| Draft ID | `EVT-A31A0CF8` |
| Title | `EVENT-004 SAFE FAKE CALENDAR PROMOTION TEST` |
| Event type | `event-004-test` |
| Start | 2026-07-20 14:00:00 -06:00 (20:00 UTC) |
| End | 2026-07-20 15:00:00 -06:00 (21:00 UTC) |
| Description | `EVENT-004 SAFE FAKE CALENDAR TEST — synthetic record for controlled system verification only.` |
| Location / private location / attendees | blank |
| Privacy | `private-review` |
| Public calendar allowed | `no` |

## Preflight

Preflight recorded CalendarLog count 12 before draft creation, an absent Google token fingerprint, and the expected pre-existing uncommitted implementation paths. The controlled proof checked the configured Calendar window and proceeded only after the renewed authorization and the promotion guard conditions were met.

## Guard design

The promotion path is draft-ID scoped and requires an authorized record with complete event fields, approved/ready routing state, `PublicCalendarAllowed=no`, `PrivacyLevel=private-review`, and no existing Calendar event ID before create. It safely updates the originating CalendarLog row with the returned Calendar ID and final state. A retry recognizes the existing ID and avoids a second Calendar insertion. Authorization state is removed immediately before the first external promotion attempt and remains non-reusable if that attempt fails; captured evidence also shows it absent after the successful promotion.

## Files changed

At evidence-capture time, the documentation task created this report and updated only the permitted root documentation files: `PROJECT_STATUS.md`, `OPERATIONS.md`, and `SECURITY_AND_PRIVACY.md`.

At evidence-capture time, the execution evidence recorded these separate, uncommitted implementation paths: `scripts/telegram_intake_router.py`, `tests/test_event_router.py`, and `tests/test_event_live_promotion_guard.py`. The externally installed plugin was changed locally for the controlled execution and must not be committed. No plugin, token/state, temporary-evidence, `docs/`, or unrelated repository path was changed by the captured documentation task. This post-capture documentation reconciliation does not alter those historical evidence labels.

## Offline tests

Final offline validation passed without live network writes:

- guard: 7 tests + 6 subtests;
- router: 21 tests + 6 subtests;
- backend: 13 tests + 6 subtests;
- privacy: 8 tests + 5 subtests;
- daily: 5 tests;
- schema: 9 tests;
- export: 9 tests + 41 subtests;
- full suite: **72 tests + 64 subtests**;
- Python compilation and diff checks: passed.

These are offline tests, not evidence of Telegram delivery or a live Calendar mutation. They independently cover the promotion guard and idempotence behavior.

## Independent pre-live checker

The independent pre-live checker passed before promotion. It verified the draft/guard conditions and the controlled target window before the one authorized create. It is separate from the offline tests and separate from the later direct installed-plugin invocation.

## Draft creation evidence

Draft `EVT-A31A0CF8` was created in CalendarLog row 14. CalendarLog total rows increased from 12 to 13. The successful create-draft audit is `AUDIT-828BE21C` (audit row 109).

## Pre-promotion row evidence

Before promotion, the draft remained on row 14 with `PrivacyLevel=private-review` and `PublicCalendarAllowed=no`. The safe routing/update sequence is evidenced by `AUDIT-F6CB20C5`, `AUDIT-8F0FE464`, and `AUDIT-9DF5AC56` (audit rows 111, 113, and 114). The final recorded row has `ApprovalStatus=created` and `Status=confirmed` after the create result was persisted.

## Live promotion evidence

The authoritative final evidence JSON supports exactly one Calendar event in the configured Calendar window: Google Calendar ID `cpq3e1oivn4ajb4t8ktemjuj0g`, exact-ID count 1, and configured-window count 1. It records status `confirmed`, summary `EVT-A31A0CF8 — EVENT-004 SAFE FAKE CALENDAR PROMOTION TEST`, empty location, and the synthetic description. The create-calendar audit is `AUDIT-537E7711` (audit row 115).

## Same-row update evidence

The returned Calendar ID was written back to the original CalendarLog row 14, not a new row. Row 14 records `CalendarEventID=cpq3e1oivn4ajb4t8ktemjuj0g`, `ApprovalStatus=created`, and `Status=confirmed`.

## Idempotent retry evidence

A direct installed-plugin retry observed during the controlled execution session returned `already_created`; that session observation is not contained in the authoritative final evidence JSON. The final JSON supports only the resulting state: 13 CalendarLog rows and exact-ID and configured-window counts of 1, not the occurrence of a retry. Offline tests independently cover idempotence.

## Privacy exclusion evidence

The authoritative final evidence JSON supports the private synthetic event's exclusion from approved-calendar output: `private_event_in_approved_calendar=false` and `approved_calendar_count=0`. It records `private-review` privacy and `PublicCalendarAllowed=no`. No public snapshot was created or published.

## /daily regression evidence

A controlled local `/daily` CLI proof observed during the execution session passed with zero writes. It left the 21 documentation files unchanged, left the repository status unchanged, and left the absent token fingerprint unchanged. This execution-session observation is not contained in the authoritative final evidence JSON, which records only final counts, hashes, and state. It is not an offline unit test, live Telegram delivery, or authorization for generation or publication.

## Authorization consumption evidence

The authoritative final evidence JSON reports `authorization_state_exists=false` after promotion. It supports only the authorization-absent final state; the execution-session observation was that consumption occurred immediately before the external attempt, so a failed attempt would not leave reusable authorization state.

## What was not done

During the controlled live-evidence execution, no public snapshot, gateway restart, plugin activation/registration change, deletion, SNC action, commit, staging, push, or unrelated live mutation was performed. No additional Calendar event was created. No human-originated Telegram message was delivered as part of this evidence. The implementation commit described below occurred after this evidence-capture boundary.

## What failed

Two initial failures were contained and repaired before the successful insertion:

1. an initial installed-plugin routing defect caused a failed routing upsert, recorded as audit `AUDIT-ABCFD8B1` (audit row 112); and
2. the original description was held as sensitive before the safe synthetic description/routing state was restored.

Neither contained failure produced an extra Calendar event. Their occurrence is not erased by the final passing checks.

## Current exact state (captured 2026-07-12)

The authoritative final evidence JSON captured at `2026-07-12T13:47:05.709393+00:00` shows one confirmed event with ID `cpq3e1oivn4ajb4t8ktemjuj0g`, linked to draft `EVT-A31A0CF8` in CalendarLog row 14. CalendarLog has 13 total rows. Authorization state and the Google token fingerprint are absent. At that capture time, it also recorded the working-tree paths `scripts/telegram_intake_router.py`, `tests/test_event_router.py`, and `tests/test_event_live_promotion_guard.py`; the implementation commit and push were then pending. This historical evidence does not assert current repository or remote status.

Direct invocation of the installed daily gateway plugin was observed during the execution session to pass with an in-memory marker and zero writes. This validates that controlled direct invocation path only and is not contained in the authoritative final evidence JSON. It was **not** a human-originated Telegram-delivered message and is not proof of Telegram transport, gateway delivery, or a real user command.

## Remaining blockers

EVENT-004 closeout is complete. Production rollout remains blocked pending any separately approved gateway/Telegram operational work. The implementation was subsequently recorded in already-pushed commit `fb2911c8e4cdc0c2c4bcf5a67fcd948db74cf174`, and this documentation/evidence closeout is recorded in `24d14a6bf5677c79a986b1c57d010cc703e71b11`. CLEANUP-003 is complete and keeps `/daily` read-only in-memory; publication remains frozen. No new Calendar promotion is authorized by this report.

## Production policy

Calendar creation remains exception-only: use draft-first intake, explicit per-event human authorization, preflight and guard checks, private-by-default fields, one scoped promotion, same-row ID persistence, idempotent retry verification, and authorization consumption. Keep public publication deny-by-default and do not treat `/daily`, direct plugin invocation, or offline tests as Calendar-promotion authority.

## Next actionable step

No further EVENT-004 closeout action is required. Obtain separate authorization before any gateway operation or future event promotion. The historical implementation and documentation commits are not authority for further live work.

## Commit hashes

- Starting commit: `871131e26275148260c26a7366ff4fd43e57144d`.
- Post-capture implementation commit (already pushed): `fb2911c8e4cdc0c2c4bcf5a67fcd948db74cf174` (`feat: add controlled event promotion authorization`). Local/origin/GitHub `main` matched immediately after that push; query current state when needed with `git rev-parse HEAD` and `git ls-remote origin refs/heads/main`.
- Documentation/evidence closeout commit: `24d14a6bf5677c79a986b1c57d010cc703e71b11` (`docs: record controlled live calendar promotion`). Query current Git and remote state when needed; this historical report does not assert a continuing remote-equality claim.

## Evidence paths and IDs

- Authoritative evidence file: `C:/Users/fallo/AppData/Local/Temp/EVENT_004_LIVE_EVIDENCE.json`
- Evidence provenance: the final JSON supports final one-event/one-row counts, authorization-absent state, and privacy facts; controlled local CLI, direct installed-plugin, and retry observations are execution-session observations, not JSON contents.
- Captured-at UTC: `2026-07-12T13:47:05.709393+00:00`
- Draft: `EVT-A31A0CF8`
- CalendarLog row: 14
- Google Calendar event: `cpq3e1oivn4ajb4t8ktemjuj0g`
- Create-draft audit: `AUDIT-828BE21C`
- Safe-update audits: `AUDIT-F6CB20C5`, `AUDIT-8F0FE464`, `AUDIT-9DF5AC56`
- Failed-routing-upsert audit: `AUDIT-ABCFD8B1`
- Calendar-create audit: `AUDIT-537E7711`
- Held original-description audit: `AUDIT-C22DA9AC` (reported by execution evidence)
