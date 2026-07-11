# Project Status — Non-Profit Hermes MVP

**Last verified:** 2026-07-11 (CLEANUP-001)

## Documentation baseline

| Item | Value |
|------|-------|
| Documentation baseline inspected | `e5abe48d425f8f079e43d2e6be43c9a5c130551e` |
| Baseline subject | `docs: establish canonical project status and supersession map` |
| Current Git revision | run `git rev-parse HEAD` |
| Current remote revision | run `git ls-remote origin refs/heads/main` |

## Current repository state

| Item | Value |
|------|-------|
| Repository | `falloutmule/non-profit-hermes-mvp` |
| Branch | `main` |
| Working tree | clean |
| Visibility | public |
| GitHub Pages source | `main /docs` (verified via `gh api .../pages`) |
| Public URL | https://falloutmule.github.io/non-profit-hermes-mvp/ |

## Command matrix

| Command | Status | Durable destination | Live proof |
|---------|--------|---------------------|------------|
| `/daily` | Live, version `website-links-dedup-003` | Reads approved-safe exports | Verified |
| `/need` | Live, draft-first | Requests tab | Verified |
| `/donation` | Live, draft-first | Donations tab | Verified |
| `/report` | Live, draft-first | Reports tab | Verified |
| `/task` | Live, draft-first | Tasks tab | Verified |
| `/inventory` | Live, upsert/draft-first | Inventory tab | Verified |
| `/event` | Live, **draft-only** | CalendarLog tab | Verified |
| Calendar promotion | Backend complete, fake-tested; **live disabled** | Google Calendar + same CalendarLog row | EVENT-004 only |

## Milestone status

| Milestone | Status |
|-----------|--------|
| EVENT-001 — Calendar publication privacy gate | Complete |
| EVENT-002 — Durable event-draft backend | Complete |
| EVENT-003 — Draft-first Telegram `/event` intake | Complete and live verified |
| EVENT-004 — Live Calendar promotion | **Unstarted** |

### Calendar creation policy

Calendar creation is **disabled** in the live `/event` plugin (`allow_calendar_creation=False`). No live Google Calendar event has been created by any `/event` flow. Calendar promotion is authorized only under EVENT-004, which has not begun.

## EVENT-003 live evidence

| Item | Value |
|------|-------|
| EventDraftID | `EVT-FC5611E9` |
| CalendarLog row | 13 |
| Create audit entry | `AUDIT-D2849AD9` |
| Update audit entry | `AUDIT-580A8E71` |
| CalendarEventID | blank |
| Google Calendar match | 0 events |
| Plugin enabled | yes |
| Gateway-active | yes |

The draft was created and then updated to:

| Field | Value |
|-------|-------|
| EventType | `telegram-test` |
| Status | `cancelled` |
| ApprovalStatus | `rejected` |
| Notes | `EVENT-003 TEST RECORD - follow-up verified` |

Implementation commit: `09e743c0084595f5e34bf820e497a4b154110929`
Evidence commit: `f5c2746c0d4f62b01d2298fc130e199579b5d9d6`

No Calendar write occurred. Only a required read-only Calendar search was performed (0 matches).

## Current public snapshot

This is a **committed publication snapshot** from the last approved-safe sync, not a live database view.

| Item | Value |
|------|-------|
| Last sync | 2026-07-11 00:26 UTC |
| Marker | `CLEAN_DOCS_DEPLOY_NON_PROFIT_HERMES_002` |
| Needs | 9 |
| Calendar events | 0 |
| Reports | 11 |
| Donations | 6 |
| Board log entries | 81 |

## Known P0 cleanup blockers

These must be resolved before EVENT-004 and before the next public snapshot is published:

1. **Schema divergence** — Backend and sync `Reports`/`Donations` header maps have diverged. A canonical shared schema module does not exist yet.
2. **Row 100 truncation** — The generic Sheet reader stops at row 100, silently omitting newer records.
3. **Donation publication gate missing** — `safe_donations()` exports every row without an explicit publication-consent field.
4. **HTML escaping** — Public HTML interpolates user-controlled Sheet values without `html.escape()`.
5. **Board-log ID exposure** — Public `approved_board_log.json` exposes internal Task/Inventory/Event IDs and audit IDs.
6. **`/daily` mutates docs/** — `run_daily_summary()` calls the sync script, which writes `docs/` files but does not commit or publish them.
7. **No deduplication in exports** — Committed JSON contains duplicate primary IDs.

See the cleanup handoff for the full P0/P1/P2/P3 plan and the staged execution order (CLEANUP-001 through CLEANUP-007).

## Test suite

| Test file | Tests |
|-----------|-------|
| `tests/test_event_router.py` | 14 |
| `tests/test_event_draft_backend.py` | 13 |
| `tests/test_event_calendar_privacy.py` | 8 |
| **Full suite** | **35 passed, 11 subtests passed** |

```
python -m pytest -q
```

## Next milestone

EVENT-004 (live Calendar promotion) is **unstarted** and blocked until P0 cleanup items are resolved and independently verified.
