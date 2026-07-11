# Development — Non-Profit Hermes MVP

**Last updated:** 2026-07-11 (CLEANUP-001)

## Prerequisites

- Python >= 3.11
- Google Cloud project with Sheets and Calendar APIs enabled
- OAuth credentials file (`google_token.json`)
- Hermes Agent running with Telegram gateway
- Git

## Repository checkout

```bash
git clone https://github.com/falloutmule/non-profit-hermes-mvp.git
cd non-profit-hermes-mvp
```

## Dependencies

This project does not yet have a `requirements.txt` or `pyproject.toml`. Current dependencies:

- `google-auth`
- `google-api-python-client`
- `pytest` (test only)

Install manually until dependency pinning is added (CLEANUP-005):

```bash
pip install google-auth google-api-python-client pytest
```

## Running tests

```bash
# Full suite
python -m pytest -q

# Compile check
python -m py_compile scripts/*.py

# Whitespace check
git diff --check
```

Current suite: **35 passed, 11 subtests passed**.

### ⚠ Test modes that write live data

**The following commands write to the live production Google Sheet:**

```bash
python scripts/non_profit_hermes_ops.py --test-write    # CREATES REAL ROWS
python scripts/telegram_intake_router.py --test          # CALLS REAL GOOGLE SERVICES
```

These are **not** offline tests. They create real records with IDs like `REQ-WRITE-TEST-001`, `DON-WRITE-TEST-001`, etc. in the production Sheet and generate real AuditLog entries.

Only run them if you intend to create test records in the live Sheet. Offline fake-based isolation is planned for CLEANUP-005.

## Test structure

| File | Tests | Scope |
|------|-------|-------|
| `tests/test_event_router.py` | 14 | Router draft-first `/event` intake, follow-up, promotion, idempotency |
| `tests/test_event_draft_backend.py` | 13 | Backend draft create/update, approval gate, Calendar promotion (fakes) |
| `tests/test_event_calendar_privacy.py` | 8 | Calendar export privacy gate, sentinel tests, two-source join |

All tests use in-memory fakes (`FakeSheetsStore`, `FakeCalendarService`). No test makes network calls.

## Code layout

```
scripts/
  non_profit_hermes_ops.py      ← Google Sheets/Calendar backend
  telegram_intake_router.py     ← Telegram intake router + /daily
  sync_approved_safe_data.py    ← approved-safe sync → docs/
tests/
  test_event_router.py
  test_event_draft_backend.py
  test_event_calendar_privacy.py
```

## Key patterns

### Draft-first intake

All write commands follow this pattern:

1. User types `/cmd <sloppy free text>`
2. Router creates a draft row (status=`needs-info`)
3. Router lists missing fields
4. User sends plain follow-up text with field=value pairs
5. Router attaches follow-up to active draft
6. When status reaches `ready`, active pointer clears

### Backend write discipline

Every write operation:
1. Calls `ensure_header()` to sync Sheet headers with code schema
2. Writes the data row
3. Calls `write_audit_log()` with actor, action, target, before/after, result

### Header-expansion pitfall

When a record type's `HEADERS` dict grows (new columns added), the live Google Sheet still has the old header row. The `ensure_header(svc, tab)` pattern writes `HEADERS[tab]` to row 1 before every `add_*`/`update_*` call to keep columns aligned.

Without this, row readers return the old column set and fields like `Status` appear as `None` even though `make_row` wrote them.

### Follow-up chain interception

Each `route_<cmd>_followup()` runs in a chain: report → task → inventory → donation → need. If ANY handler returns a `RouterResult` (even for "no draft found"), the chain stops and downstream handlers never execute.

The fix: before looking up drafts, check if the follow-up contains command-specific fields. If no relevant fields AND no active draft, return `None` to let the chain continue.

## Known issues (cleanup backlog)

See [PROJECT_STATUS.md](PROJECT_STATUS.md) § "Known P0 cleanup blockers" for the full list. Key development-facing issues:

- **Schema divergence**: backend and sync header maps have diverged. Canonical shared schema module needed.
- **Row 100 truncation**: generic Sheet reader stops at row 100.
- **No dependency manifest**: no `requirements.txt` or `pyproject.toml`.
- **No CI**: no automated checks on push.
- **Hardcoded paths**: machine-specific paths in source code.
- **`/daily` mutates docs/**: daily summary calls sync, which writes files.

## Plugin development

Plugins are thin shims that live outside this repository. See the [non-profit-hermes skill](https://github.com/falloutmule/non-profit-hermes-mvp) for the plugin pattern:

1. Plugin registers the command
2. Plugin calls the router with `source_link` and appropriate flags
3. Plugin renders via `_result_to_text()`
4. Plugin contains no direct Sheets/Calendar writes

Plugin reproducibility from GitHub is planned for CLEANUP-005.
