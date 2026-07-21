# Development — Non-Profit Hermes MVP

**Current development boundary captured:** 2026-07-21

## Prerequisites

Current source assumes:

- Python 3.11 or newer;
- `google-auth`;
- `google-api-python-client`;
- `pytest` for tests;
- Git;
- Hermes Agent for runtime integration.

There is currently no `requirements.txt`, `pyproject.toml`, installable Python package, unified plugin, profile distribution, or runtime doctor. A developer must provide dependencies manually until later packaging work implements and verifies those artifacts.

## Source layout

```text
scripts/
  telegram_intake_router.py        command parsing, draft/follow-up routing, /daily
  non_profit_hermes_ops.py         Sheets/Calendar mutations and AuditLog
  non_profit_hermes_schema.py      canonical Sheet schema and publication predicates
  sync_approved_safe_data.py       approved-safe collection and docs generation
  google_oauth_refresh.py          atomic credential refresh persistence
  install_runtime_plugins.py       dry-run-by-default legacy plugin installer
  check_runtime_plugin_drift.py    read-only canonical/installed comparison
runtime_plugins/                   seven canonical legacy plugin copies
RUNTIME_PLUGIN_MANIFEST.json       canonical file hashes and mutable patterns
tests/                             offline fake-based regression suite
docs/                              generated/public GitHub Pages output
reports/                           current and historical evidence
```

Operational modules and all seven legacy plugin entrypoints still contain user-specific path assumptions and `sys.path` mutation. Do not copy those patterns into new code. Portability is a later bounded implementation task.

## Tests

Run the exact repository lane:

```bash
python -m pytest -q
```

Current verified baseline:

```text
235 passed, 64 subtests passed
```

Focused read-only daily lane:

```bash
python -m pytest -q tests/test_daily_read_only.py
```

Current focused baseline: 5 passed.

Additional static checks:

```bash
python -m py_compile scripts/*.py tests/*.py
git diff --check
```

`pytest.ini` limits collection to `tests/` and excludes linked `worktrees/`. Do not weaken this policy or run an alternate lane as a substitute for the required root command.

Older test counts in historical CLEANUP and EVENT reports describe their own commits only. They are not the current baseline.

## Test safety

The pytest suite uses fakes and synthetic temporary files. It does not make live Telegram, Google Sheets, Google Calendar, gateway, or publication calls.

The following are operational modes, not unit tests:

```bash
python scripts/non_profit_hermes_ops.py --test-write
python scripts/telegram_intake_router.py --test
python scripts/sync_approved_safe_data.py
```

They may access or mutate live systems/files and require explicit authorization. `sync_approved_safe_data.py --dry-run` reads configured live sources but does not write generated files.

## Schema and privacy development rules

- `scripts/non_profit_hermes_schema.py` is the canonical Sheet header and publication-predicate source.
- Append new columns; do not reorder existing live columns without a migration.
- Every mutation must produce an AuditLog entry.
- Tasks and Inventory remain internal-only.
- Automated report writes must not populate sensitive-detail fields.
- Requests, Donations, and Reports are deny-by-default for export.
- Escape every user-controlled value rendered into public HTML.
- `/daily` must remain in-memory and read-only; it must not call the public writer.
- Calendar creation must remain behind exact per-event authorization and idempotence guards.

## OAuth refresh development rules

Durable credential refresh goes through `refresh_and_persist_credential()` and its candidate/validation/lock/backup/atomic-replace/rollback contract. Do not reintroduce direct token overwrites. Keep errors and evidence secret-free.

Read-only paths must opt out of durable persistence. `/daily` uses `persist_refresh=False`; sync `--dry-run` does the same. Tests for refresh persistence use synthetic files only.

## Legacy plugin development

`runtime_plugins/` is canonical source for the seven current plugins. Any intended plugin-source change must also update `RUNTIME_PLUGIN_MANIFEST.json` and the focused parity/install tests.

Verify without writes:

```bash
python scripts/install_runtime_plugins.py --dry-run
python scripts/check_runtime_plugin_drift.py --installed-root <plugin-root> --json --strict
```

Do not edit installed plugin copies directly and then treat them as source. Do not run installer `--apply` against the live root during ordinary development.

## Generated artifacts

`docs/` and `docs/data/` are generated public output. Do not hand-edit them. A task that changes generation must run the generator only when production-data reads and generated-file changes are authorized, review exact source/output parity, and test the release artifact. This documentation-only reconciliation intentionally leaves `docs/` unchanged.

## Packaging work in progress

The approved later target is an importable `non_profit_hermes` package, one unified seven-command plugin, an installable secret-free profile distribution, and a deterministic doctor. None exists yet. Do not document proposed filenames, commands, or install flows as available until implementation and clean-install acceptance pass.
