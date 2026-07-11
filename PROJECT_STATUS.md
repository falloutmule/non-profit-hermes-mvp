# Project Status — Non-Profit Hermes MVP

**Last verified:** 2026-07-11 13:48 MDT (CLEANUP-002 closeout)

## Current repository state

| Item | Value |
|---|---|
| Repository | `falloutmule/non-profit-hermes-mvp` |
| Branch | `main` |
| Implementation commit (historical) | `9626aaa23cb390493290edc7e92d2e048d80bab7` |
| CLEANUP-002 closeout commit (historical) | `0bae419c0f7f6173beb0545c163cc9e1d0d028c1` |
| Current Git revision | Query when needed: `git rev-parse HEAD` |
| Current remote `main` revision | Query when needed: `git ls-remote origin refs/heads/main` |
| Visibility | public |
| GitHub Pages source | `main /docs` |

## CLEANUP-002

**Complete.** `9626aaa` resolved the canonical-schema divergence, row-100 truncation, request/report/donation deny-by-default publication gates, HTML escaping, board-log internal-ID exposure, and export deduplication.

The full suite passed: **53 passed, 52 subtests passed**. Post-repair independent implementation checking returned **PASS** on 2026-07-11 13:48 MDT.

The controlled live `--dry-run` observed zero approved public needs, donations, and reports. The four generated approved-safe JSON files were inspected and restored because no public snapshot publication was authorized. No automatic approval backfill occurred.

## Command and publication status

| Command or workflow | Current state |
|---|---|
| `/daily` | Live, but its mutation/generation coupling remains the sole P0 cleanup concern |
| `/need`, `/donation`, `/report`, `/task`, `/inventory` | Live, draft-first |
| `/event` | Live, draft-only; Calendar promotion remains disabled |
| Approved-safe public snapshot | Frozen pending CLEANUP-003 |

Publication is frozen until CLEANUP-003 separates `/daily` from generation. No new public snapshot is authorized from the current live records, and there is no automatic approval backfill.

## Retained historical evidence

EVENT-003 live verification created and updated draft `EVT-FC5611E9` in CalendarLog row 13, with `CalendarEventID` blank and a read-only Calendar search returning zero matches. Its implementation commit is `09e743c0084595f5e34bf820e497a4b154110929`; its evidence commit is `f5c2746c0d4f62b01d2298fc130e199579b5d9d6`. This is historical draft-only evidence, not authorization for EVENT-004.

The prior committed approved-safe snapshot (2026-07-11 00:26 UTC; marker `CLEAN_DOCS_DEPLOY_NON_PROFIT_HERMES_002`) recorded needs 9, Calendar events 0, reports 11, donations 6, and board-log entries 81. It is a historical publication snapshot, not a live-data view and not an authorized new publication.

## Milestones

| Milestone | Status |
|---|---|
| EVENT-001 — Calendar publication privacy gate | Complete |
| EVENT-002 — Durable event-draft backend | Complete |
| EVENT-003 — Draft-first Telegram `/event` intake | Complete and live verified |
| CLEANUP-002 — Export safety | Complete (`9626aaa`) |
| CLEANUP-003 — Separate `/daily` from generation | Next |
| EVENT-004 — Live Calendar promotion | **Unstarted and blocked** |

EVENT-004 has not enabled Calendar promotion, plugin activation, gateway refresh/restart, Telegram registration, or live Telegram testing.

## Test suite

```bash
python -m pytest -q
```

Current result: **53 passed, 52 subtests passed**.
