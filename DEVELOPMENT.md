# Development — Non-Profit Hermes MVP

**Last updated:** 2026-07-11 13:48 MDT (CLEANUP-002 closeout)

## Prerequisites

- Python >= 3.11
- Google Cloud project with Sheets and Calendar APIs enabled
- OAuth credentials file (`google_token.json`)
- Hermes Agent running with Telegram gateway
- Git

## Tests

```bash
# Full suite
python -m pytest -q

# Compile check
python -m py_compile scripts/*.py tests/*.py

# Whitespace check
git diff --check
```

CLEANUP-002 result: **53 passed, 52 subtests passed**.

CLEANUP-002 added two export-safety test modules:

- `tests/test_schema_parity.py` — canonical schema parity and append-order behavior
- `tests/test_export_safety.py` — deny-by-default gates, full-range reads beyond row 100, deduplication, HTML escaping, board-log aggregation, and dry-run no-write behavior

## Canonical schema and export generation

`scripts/non_profit_hermes_schema.py` owns the canonical Sheet header definitions used by both write and export paths. New columns are appended; CLEANUP-002 added `Reports!V1 = PublicSummaryAllowed` and `Donations!V1:X1 = PrivacyLevel, PublicListingAllowed, LastUpdated` without changing existing data rows.

Generate approved-safe data explicitly:

```bash
python scripts/sync_approved_safe_data.py
```

Inspect without filesystem writes:

```bash
python scripts/sync_approved_safe_data.py --dry-run
```

`--dry-run` reads the configured Sheet ranges and reports acceptance/rejection, duplicate, and row-count evidence without writing generated public files. The controlled CLEANUP-002 dry-run found zero approved public needs, donations, and reports in the observed live records.

Exports use canonical IDs plus newest `LastUpdated` deduplication before deny-by-default publication gates. Requests require `ConsentToShare`; Donations require `PublicListingAllowed`; Reports require `PublicSummaryAllowed` and `PublicSummaryDraft`. Public HTML escapes user-controlled values, and board logs are aggregate-only.

## Code layout

```text
scripts/
  non_profit_hermes_ops.py      ← Google Sheets/Calendar backend
  non_profit_hermes_schema.py   ← canonical Sheet schema
  telegram_intake_router.py     ← Telegram intake router + /daily
  sync_approved_safe_data.py    ← approved-safe export generation
tests/
  test_schema_parity.py
  test_export_safety.py
  test_event_router.py
  test_event_draft_backend.py
  test_event_calendar_privacy.py
```

## Remaining development boundary

CLEANUP-003 is next: separate `/daily` from generation behavior. Until then, publication is frozen; do not treat a `/daily` invocation as authorization to create or publish a public snapshot. There is no automatic approval backfill.

EVENT-004 remains unstarted and blocked. It has not enabled live Calendar promotion, plugin activation, gateway refresh/restart, Telegram registration, or a live Telegram test.
