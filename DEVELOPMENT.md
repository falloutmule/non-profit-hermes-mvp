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

The repository has `pyproject.toml`, the importable `non_profit_hermes` package, the canonical unified v1.0.0 plugin, a supported root-level v1.0.0 Hermes profile distribution, and a deterministic offline/live-readonly runtime doctor. Clean-install, independent-checker, actual production doctor, and production-migration acceptance remain later gates.

## Source layout

```text
non_profit_hermes/                 portable package-owned runtime behavior
  diagnostics.py                  typed doctor checks, aggregation, redaction, exit codes
  live_diagnostics.py             injected/default read-only integration probes
  doctor.py                       module and console-script CLI
plugins/non-profit-hermes/         canonical unified v1.0.0 seven-command plugin
distribution.yaml                  supported profile-distribution manifest
SOUL.md                            sanitized nonprofit operating identity
config.yaml                        secret-free profile defaults
skills/non-profit-hermes/          bundled seven-command operating skill
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
363 passed, 69 subtests passed
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

Focused distribution/package/plugin lane:

```bash
python -m pytest -q tests/test_profile_distribution.py tests/test_unified_plugin.py tests/test_portable_package_integration.py
python -m py_compile non_profit_hermes/*.py plugins/non-profit-hermes/*.py tests/test_profile_distribution.py
```

Focused doctor lane:

```bash
python -m pytest -q tests/test_doctor_live_readonly.py tests/test_doctor_offline.py tests/test_profile_distribution.py
python -m py_compile non_profit_hermes/*.py tests/test_doctor_live_readonly.py tests/test_doctor_offline.py
```

Doctor integration tests must inject fakes or monkeypatch only the explicit process, URL, Google, Scheduled Task, and runtime-status boundaries. They must snapshot credential/profile/public files before and after probes, assert the exact read-only call ledger, and prove redaction. Do not run the default live adapter against production during ordinary development.

Focused clean-install harness lane:

```bash
python -m pytest -q tests/test_clean_install_acceptance.py tests/test_doctor_offline.py tests/test_profile_distribution.py tests/test_portable_package_integration.py
python -m py_compile scripts/clean_install_acceptance.py tests/test_clean_install_acceptance.py
python scripts/clean_install_acceptance.py --help
```

Unit tests never execute the real harness. They fake subprocess/filesystem boundaries and verify admission refusal, archive traversal protection, secret-free inventory, isolated environment construction, exact argv, wheel/sdist rules, doctor equivalence, command registration, nonmutation, deterministic evidence, and first-failure behavior. The separately run harness recreates a disposable Git index from the already-scanned archive because parity tests require an index; it never copies the source `.git` directory.

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

## Profile distribution development

The repository root is the distribution root. `distribution.yaml`, `SOUL.md`, `config.yaml`, `skills/non-profit-hermes/`, and `plugins/non-profit-hermes/` are the authored payload. A `profile/` nesting layer is unsupported by the installed Hermes distribution schema and must not be introduced.

Keep `distribution_owned` explicit and limited to the manifest, SOUL, safe config, bundled skill, and unified plugin. Keep environment requirements to names, descriptions, and required flags; never add real identifiers, paths, credentials, or provider secrets as defaults. `auth.json`, `.env`, user data, state, caches, backups, and `local/` remain excluded and user-owned.

The profile manifest has no Python dependency-install field. The `non_profit_hermes` package must be installed separately before the profile distribution. Do not add an unsupported manifest key or installation hook to hide this prerequisite.

All install, collision, update, force-config, force-install, preflight-failure, and plugin-registration tests must isolate both `Path.home()` and `HERMES_HOME` under `tmp_path`. Tests must never install, update, or delete an actual profile, enable a live plugin, start a gateway, call Telegram or Google, create a Calendar event, or generate public files.

Normal updates preserve local `config.yaml`; the `--force-config` path replaces it. Both paths preserve `.env`, `auth.json`, memories, sessions, databases, logs, and `local/`. The installed core guarantees no owned-file changes on a failed compatibility preflight, but does not expose a general mid-copy transactional rollback API. Document rollback at the reviewed Git checkout, package reinstall, profile force-install, backup, and operator-verification layer rather than patching Hermes core or claiming a stronger guarantee.

The profile distribution, unified plugin, and runtime doctor now exist in source and have offline/fake-backed builder verification. Clean-install acceptance, independent checker verdict, published tag, actual profile installation, production live-readonly doctor, gateway activation, and production migration remain pending. Do not describe the unified plugin or doctor as production-accepted until those later gates pass.
