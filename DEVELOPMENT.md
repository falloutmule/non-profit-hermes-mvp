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

The repository now has `pyproject.toml`, the importable `non_profit_hermes` package, and the canonical unified v1.0.0 plugin. Profile-distribution, runtime-doctor, clean-install, and production-migration acceptance remain later gates.

## Source layout

```text
non_profit_hermes/                 portable package-owned runtime behavior
plugins/non-profit-hermes/         canonical unified v1.0.0 seven-command plugin
scripts/
  telegram_intake_router.py        compatibility entrypoint for command routing
  non_profit_hermes_ops.py         compatibility entrypoint for operations
  sync_approved_safe_data.py       compatibility entrypoint for approved-safe sync
  install_runtime_plugins.py       unified-first, dry-run-by-default plugin installer
  check_runtime_plugin_drift.py    source-aware, read-only canonical/installed comparison
runtime_plugins/                   seven deprecated one-release rollback shims
RUNTIME_PLUGIN_MANIFEST.json       v2 modes, source paths, roles, hashes, mutable patterns
tests/                             offline fake-based regression suite
docs/                              generated/public GitHub Pages output
reports/                           current and historical evidence
```

Runtime behavior belongs in `non_profit_hermes`; compatibility scripts and plugin shims must stay thin. Do not add user-specific paths or `sys.path` mutation.

## Tests

Run the exact repository lane:

```bash
python -m pytest -q
```

Current verified baseline:

```text
323 passed, 69 subtests passed
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

## Unified and compatibility plugin development

`plugins/non-profit-hermes/` is the canonical v1.0.0 runtime plugin. The seven `runtime_plugins/` entries are deprecated compatibility shims retained for one release and deterministic rollback only. Unified and legacy modes expose the same command names, so they must never be enabled together.

Any intended unified or shim source change must also update its exact hashes in `RUNTIME_PLUGIN_MANIFEST.json` and the focused parity/install/drift tests. Manifest source paths must remain normalized repository-relative paths, and every manifest identity/version must match the corresponding `plugin.yaml`.

Verify without writes:

```bash
python scripts/install_runtime_plugins.py --dry-run
python scripts/install_runtime_plugins.py --dry-run --mode legacy
python scripts/check_runtime_plugin_drift.py --installed-root <plugin-root> --json --strict
python scripts/check_runtime_plugin_drift.py --installed-root <plugin-root> --mode legacy --json --strict
python scripts/check_runtime_plugin_drift.py --installed-root <plugin-root> --mode all --json
```

Default installer and checker mode is `unified`; `--mode legacy` selects only the seven rollback shims; drift `--mode all` audits both sets without writing. The installer never enables, disables, or removes plugins. Any migration must disable the opposite set before gateway start. Do not edit installed copies and then treat them as source, and do not run installer `--apply` against the live root during ordinary development. Live apply requires later migration authorization and explicit `--live`.

## Generated artifacts

`docs/` and `docs/data/` are generated public output. Do not hand-edit them. A task that changes generation must run the generator only when production-data reads and generated-file changes are authorized, review exact source/output parity, and test the release artifact. This documentation-only reconciliation intentionally leaves `docs/` unchanged.

## Packaging work in progress

The importable `non_profit_hermes` package and unified seven-command plugin now exist in source and have offline builder verification. An installable secret-free profile distribution, deterministic doctor, clean-install acceptance, independent checker verdict, and production migration remain pending. Do not describe the unified plugin as installed, enabled, live-migrated, or production-accepted until those later gates pass.
