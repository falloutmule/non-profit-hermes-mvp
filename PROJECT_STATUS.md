# Project Status — Non-Profit Hermes MVP

**Last updated:** 2026-07-12 (EVENT-004 closeout; see `EVENT_004_LIVE_CALENDAR_PROMOTION_REPORT.md`)

## Current repository state

| Item | Value |
|---|---|
| Repository | `falloutmule/non-profit-hermes-mvp` |
| Branch | `main` |
| Implementation commit (historical) | `9626aaa23cb390493290edc7e92d2e048d80bab7` |
| CLEANUP-002 closeout commit (historical) | `0bae419c0f7f6173beb0545c163cc9e1d0d028c1` |
| EVENT-004 starting commit (historical) | `871131e26275148260c26a7366ff4fd43e57144d` |
| EVENT-004 implementation commit (historical, already pushed) | `fb2911c8e4cdc0c2c4bcf5a67fcd948db74cf174` — `feat: add controlled event promotion authorization`; local/origin/GitHub `main` matched immediately after its push |
| EVENT-004 evidence/documentation closeout commit (historical) | `24d14a6bf5677c79a986b1c57d010cc703e71b11` — `docs: record controlled live calendar promotion`; query current Git/remote state when needed rather than relying on this table |
| Current Git revision | Query when needed: `git rev-parse HEAD` |
| Current remote `main` revision | Query when needed: `git ls-remote origin refs/heads/main` |
| Visibility | public |
| GitHub Pages source | `main /docs` |

## CLEANUP-002 retained baseline

**Complete.** `9626aaa` resolved the canonical-schema divergence, row-100 truncation, request/report/donation deny-by-default publication gates, HTML escaping, board-log internal-ID exposure, and export deduplication.

The CLEANUP-002 closeout suite passed: **53 passed, 52 subtests passed**. Post-repair independent implementation checking returned **PASS** on 2026-07-11 13:48 MDT.

The controlled live `--dry-run` observed zero approved public needs, donations, and reports. The four generated approved-safe JSON files were inspected and restored because no public snapshot publication was authorized. No automatic approval backfill occurred.

## EVENT-004 — controlled live Calendar promotion

**EVENT-004 is fully complete; production rollout remains blocked.** The authoritative final evidence JSON captured 2026-07-12 supports one synthetic draft, `EVT-A31A0CF8`, promoted to the configured Google Calendar: confirmed event ID `cpq3e1oivn4ajb4t8ktemjuj0g`, persisted to CalendarLog row 14, with configured-window and exact-ID counts each 1. A direct installed-plugin retry observed during the execution session returned `already_created`; the JSON records the final one-event/13-row state, not retry occurrence.

The final JSON supports the private event's exclusion from approved-calendar output (`approved_calendar_count=0`) and authorization-absent state after promotion. The final offline suite passed **72 tests and 64 subtests**. Controlled local `/daily` CLI and direct installed-plugin daily invocation passed with zero writes during the execution session; those observations are not contained in the JSON. Neither was a human-originated Telegram-delivered message or proves Telegram transport.

Initial plugin-routing and sensitive-description-hold failures were contained and repaired before the one successful insertion. Full evidence, limitations, audit IDs, and operating policy are in `EVENT_004_LIVE_CALENDAR_PROMOTION_REPORT.md`.

## Command and publication status

| Command or workflow | Current state |
|---|---|
| `/daily` | Live for operations summaries; controlled local execution-session proof passed zero writes (not a final-JSON observation); completed CLEANUP-003 keeps it read-only in-memory with no generation or publication mutation |
| `/need`, `/donation`, `/report`, `/task`, `/inventory` | Live, draft-first |
| `/event` | Draft-first; one controlled EVENT-004 Calendar promotion completed under consumed, per-event authorization; no continuing promotion authority |
| Approved-safe public snapshot | Frozen; CLEANUP-003 is complete and does not authorize generation or publication |

Publication remains frozen. Completed CLEANUP-003 keeps `/daily` read-only in-memory; no new public snapshot is authorized from the current live records, and there is no automatic approval backfill.

## Retained historical evidence

EVENT-003 live verification created and updated draft `EVT-FC5611E9` in CalendarLog row 13, with `CalendarEventID` blank and a read-only Calendar search returning zero matches. Its implementation commit is `09e743c0084595f5e34bf820e497a4b154110929`; its evidence commit is `f5c2746c0d4f62b01d2298fc130e199579b5d9d6`. This is historical draft-only evidence, not authorization for EVENT-004.

The prior committed approved-safe snapshot (2026-07-11 00:26 UTC; marker `CLEAN_DOCS_DEPLOY_NON_PROFIT_HERMES_002`) recorded needs 9, Calendar events 0, reports 11, donations 6, and board-log entries 81. It is a historical publication snapshot, not a live-data view and not an authorized new publication.

## Milestones

| Milestone | Status |
|---|---|
| EVENT-001 — Calendar publication privacy gate | Complete |
| EVENT-002 — Durable event-draft backend | Complete |
| EVENT-003 — Draft-first Telegram `/event` intake | Complete and live verified |
| EVENT-004 — Controlled live Calendar promotion | Fully complete; implementation commit `fb2911c` and evidence/documentation closeout commit `24d14a6` recorded; production rollout remains blocked and future promotions require new per-draft authorization |
| CLEANUP-002 — Export safety | Complete (`9626aaa`) |
| CLEANUP-003 — Separate `/daily` from generation | Complete |

## Test suite

```bash
python -m pytest -q
```

Latest EVENT-004 final offline result: **72 passed, 64 subtests passed**. Offline results independently cover idempotence; controlled local/direct-plugin execution-session proofs are distinct from the final JSON and from human-originated Telegram delivery proof.
