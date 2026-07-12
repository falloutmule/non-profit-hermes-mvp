# CLEANUP-004 Runtime Plugin Reproducibility Report

**Recorded:** 2026-07-12T15:33:01Z
**Scope:** canonical, tracked copies of the seven installed non-profit Hermes plugins and offline reproducibility tooling. No commit or push was performed.

## Preconditions and source capture

- Before edits, `main`, `HEAD`, and `origin/main` were all `5b533fcbfa18df6846ebf7a5a14ba5802a4b70de`; `git status --porcelain=v1` was empty.
- Installed source was read from `C:\Users\fallo\AppData\Local\hermes\plugins` only for: `daily`, `event`, `need`, `donation`, `report`, `task`, and `inventory`.
- Canonical sources exclude `__pycache__` and contain only source/metadata files: daily 3, event 2, need 2, donation 3, report 2, task 2, inventory 2.
- A marker-only review found no actual secret-bearing source. One event-source token reference was classified as a non-secret reference; no secret value was read or recorded.

## Deliverables

- `runtime_plugins/` holds the seven canonical plugin directory copies.
- `RUNTIME_PLUGIN_MANIFEST.json` lists every canonical file and SHA-256 digest, with `__pycache__/**` declared mutable/derived state.
- `scripts/check_runtime_plugin_drift.py` is read-only. It supports default text, `--json`, `--installed-root`, and `--strict`; its classifications are `MATCH`, `EXPECTED DERIVATION`, `EXPLAINED MUTABLE STATE`, `UNEXPLAINED DRIFT`, `MISSING`, and `UNTESTED`.
- `scripts/install_runtime_plugins.py` verifies the manifest, is dry-run by default, requires both `--apply` and `--target-root` to write, blocks the live root unless `--live` is separately supplied, blocks dirty Git unless deliberately overridden, creates a backup before replacement, atomically replaces plugin directories, and preserves declared mutable paths.

## Evidence and temporary-target proof

- Read-only comparison evidence: `C:\Users\fallo\AppData\Local\Temp\CLEANUP_004_COMPARISON_EVIDENCE.json`.
- Installed non-bytecode hashes were captured before at `2026-07-12T15:31:03.035722Z` in `C:\Users\fallo\AppData\Local\Temp\CLEANUP_004_INSTALLED_HASHES_BEFORE.json` and after at `2026-07-12T15:31:44.892891Z` in `C:\Users\fallo\AppData\Local\Temp\CLEANUP_004_INSTALLED_HASHES_AFTER.json`. The seven plugin hash maps were identical.
- Successful temporary-only reinstall proof: `C:\Users\fallo\AppData\Local\Temp\CLEANUP_004_PLUGIN_REINSTALL\mutable_20260712T153144Z`.
  - The daily target began with a declared mutable `__pycache__/retained.pyc`.
  - The installer created a backup before overwrite and retained that declared mutable bytecode file.
  - Strict drift check returned only `EXPECTED DERIVATION` for that retained bytecode and `MATCH` for the remaining temporary targets; strict mode exited zero.
- No installer invocation used `--live`; the installed plugin root was never a write target.

## Offline verification

| Command | Result |
| --- | --- |
| `python -m pytest tests/test_runtime_plugin_drift.py tests/test_runtime_plugin_install.py tests/test_runtime_plugin_behavior_parity.py -q` | `9 passed in 0.78s` |
| `python -m pytest tests/test_event_live_promotion_guard.py tests/test_event_router.py tests/test_daily_read_only.py tests/test_event_calendar_privacy.py tests/test_event_draft_backend.py -q` | `54 passed, 23 subtests passed in 0.61s` |
| `python -m pytest -q` | `81 passed, 64 subtests passed in 1.22s` |
| `python -m py_compile scripts/check_runtime_plugin_drift.py scripts/install_runtime_plugins.py tests/test_runtime_plugin_drift.py tests/test_runtime_plugin_install.py tests/test_runtime_plugin_behavior_parity.py` | passed |
| `git diff --check` | passed |
| live-root `check_runtime_plugin_drift.py --strict` | passed; all observed differences were expected `__pycache__` derivations |

The behavior-parity test is intentionally offline: it verifies byte-for-byte canonical/installed equality for every manifest source/metadata file without importing plugins or contacting Telegram, Google, or a gateway.

## Runtime and external-service limits

A process listing at 2026-07-12T15:33:01Z showed Hermes desktop processes with PIDs `4234744`, `4196124`, `4220832`, `4221948`, and `4211904`. This is process-existence evidence only; it does **not** prove gateway command registration, plugin activation, Telegram delivery, or Google integration. No Google, Telegram, plugin registration, gateway, authorization, or installed-plugin mutation was performed.

## Final working-tree state

The intended uncommitted additions are `RUNTIME_PLUGIN_MANIFEST.json`, `runtime_plugins/**`, both new scripts, all three focused tests, and this report. No commit or push was made.
