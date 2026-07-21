# Unified Non-Profit Hermes Plugin Report

## Scope

NPH-V1-030A freezes the canonical unified plugin interface at `plugins/non-profit-hermes`. NPH-V1-030B1 converts the seven historical plugins into deprecated one-release compatibility shims. NPH-V1-030B2 makes manifest v2, installation, and drift checks unified-first while retaining a deterministic legacy-only rollback mode. None of these slices installed, enabled, or invoked a plugin in a live Hermes profile. The unified plugin registers only `/daily`, `/need`, `/donation`, `/report`, `/task`, `/inventory`, and `/event`, and delegates every handler through `non_profit_hermes.router.run_plugin_command(name, raw_args)`.

## Schema and API basis

- Installed runtime: `Hermes Agent v0.18.2 (2026.7.7.2)`, upstream `413ed6b9`, Python 3.11.9.
- Current user guide checked 2026-07-21: <https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins>
- Current developer guide checked 2026-07-21: <https://hermes-agent.nousresearch.com/docs/developer-guide/plugins>
- Installed source checked at `hermes_cli/plugins.py`: `PluginContext.register_command(name, handler, description="", args_hint="")`; handlers receive one raw argument string.
- Manifest uses only the supported standalone fields needed by this plugin: `name`, `version`, `description`, and `kind`.
- Manifest identity is exactly `name: non-profit-hermes`, `version: 1.0.0`, `kind: standalone`.
- General plugins remain opt-in; this task performed no activation.

## RED

The package-adapter tests were added first and run before implementation:

```text
python -m pytest -q tests/test_event_router.py::EventRouterTests::test_plugin_boundary_preserves_ordinary_event_and_exact_promotion_dispatch tests/test_event_router.py::EventRouterTests::test_plugin_boundary_rejects_malformed_promotion_without_router_dispatch tests/test_daily_read_only.py::DailyReadOnlyTests::test_plugin_daily_boundary_stays_in_memory_and_read_only
```

Expected RED: `run_plugin_command` was absent. Result: `7 failed, 1 passed` as reported by pytest's subtest accounting, with the failures caused by `AttributeError: module 'non_profit_hermes.router' has no attribute 'run_plugin_command'`.

After the package boundary reached GREEN, unified-plugin tests were added before plugin files existed:

```text
python -m pytest -q tests/test_unified_plugin.py
```

Expected RED: canonical plugin files were absent. Result: `12 failed`, all rooted in missing `plugins/non-profit-hermes/plugin.yaml` or Python entrypoint files.

## GREEN

Package adapter tracer:

```text
python -m pytest -q tests/test_event_router.py::EventRouterTests::test_plugin_boundary_preserves_ordinary_event_and_exact_promotion_dispatch tests/test_event_router.py::EventRouterTests::test_plugin_boundary_rejects_malformed_promotion_without_router_dispatch tests/test_daily_read_only.py::DailyReadOnlyTests::test_plugin_daily_boundary_stays_in_memory_and_read_only
3 passed, 5 subtests passed
```

Unified plugin tracer:

```text
python -m pytest -q tests/test_unified_plugin.py
12 passed
```

## NPH-V1-030B1 compatibility shims

Commit `02e2e406e950ecc57d344c31a67f56304a174afe` (`refactor: make legacy plugins compatibility shims`, parent `2cc294760b53bcfd98c97399d37ae814d9a65585`) converted all seven historical directories into v1.0.0 compatibility shims. Each shim registers one preserved command and delegates through the same package router boundary as the unified plugin. The obsolete duplicate `init.py` entrypoints were removed.

B1 RED:

```text
python -m pytest -q tests/test_legacy_plugin_shims.py tests/test_runtime_plugin_behavior_parity.py
19 failed, 2 passed
```

The failures demonstrated old manifests and handlers, duplicate entrypoints, unsafe error output, and missing deterministic offline parity. That first RED reached one old absolute-path handler and surfaced `REFRESH_PERSISTENCE_FILE_FLUSH_FAILED`; no successful external mutation was confirmed, and the old path was not repeated.

B1 GREEN and verification:

```text
new shim/parity slice: 21 passed
required focused lane: 46 passed in 3.86s
full suite: 314 passed, 69 subtests passed in 10.79s
```

The final parity fixture imports tracked unified and shim sources under isolated names with fake contexts. Manifest parity covered seven plugins and 14 exact Git-blob files. No installed-runtime copy was used.

## NPH-V1-030B2 manifest and mode TDD

B2 is the scoped commit with subject `feat: make unified plugin installer default` and required parent `02e2e406e950ecc57d344c31a67f56304a174afe`.

Tests were added first and observed failing for each missing contract:

- manifest v2/unified-first RED: schema remained the legacy CLEANUP-004 manifest;
- unified installer RED: source resolution still assumed `runtime_plugins/`;
- legacy mode RED: `--mode legacy` was unrecognized;
- source-safety RED: an unsafe absolute source was accepted;
- identity/version RED: manifest identity mismatch was accepted;
- duplicate-exposure RED: unified and compatibility entries could be selected together;
- drift RED: the checker inspected only the legacy source layout.

Each tracer reached GREEN before the next behavior was added. The final B2 focused lane is:

```text
python -m pytest -q tests/test_runtime_plugin_install.py tests/test_runtime_plugin_drift.py tests/test_runtime_plugin_behavior_parity.py tests/test_legacy_plugin_shims.py tests/test_unified_plugin.py
55 passed in 7.90s
```

NPH-V1-030A required focused lane:

```text
python -m pytest -q tests/test_unified_plugin.py tests/test_event_router.py tests/test_daily_read_only.py
41 passed, 11 subtests passed
```

## Registration contract

Registration was proven with a Hermes-compatible package import fixture and fake plugin contexts:

1. exact command order: `daily`, `need`, `donation`, `report`, `task`, `inventory`, `event`;
2. exact preserved descriptions and argument hints;
3. seven unique names only;
4. a second `register(ctx)` call on the same context adds no duplicates;
5. a new context registers all seven independently;
6. import and registration do not execute the router boundary;
7. no tools, hooks, CLI commands, Google behavior, credential requirements, or environment gates are registered.

The same fixture runs in a subprocess from a pytest temporary directory with only the repository on normal `PYTHONPATH`; no repository-path injection or current-working-directory assumption is used.

## Offline parity and safety

- Every handler is a thin closure over the same package-owned `run_plugin_command` boundary and returns its output unchanged.
- The package boundary prefixes ordinary command payloads with the selected slash command and preserves the existing renderer.
- Ordinary `/event` payloads remain draft commands.
- Only an exact two-field payload containing one valid `EVT-XXXXXXXX` identifier and one truthy `create_calendar` or `confirm_create` field is dispatched raw to the existing one-shot local authorization path.
- Promotion-shaped payloads with missing, false, duplicated, malformed, non-event, or extra fields fail closed before router dispatch.
- Calendar creation remains disabled except for the pre-existing exact one-shot local authorization guard; no permanent enablement was added.
- `/daily` continues through the in-memory approved-safe snapshot. Tests reject write-service initialization and public JSON/HTML generation.
- Unexpected handler exceptions return a stable command-specific message. Exception text, traceback text, paths, and private sentinel values are not returned.
- Registration and import made zero router executions, Google calls, network calls, file writes, credential reads, or external state initialization in the verified fixtures.

## NPH-V1-030A full verification

```text
python -m pytest -q
295 passed, 69 subtests passed in 11.27s
```

Additional package/router compatibility lane:

```text
python -m pytest -q tests/test_router_package_compat.py tests/test_operations_package_compat.py tests/test_event_live_promotion_guard.py
23 passed, 6 subtests passed
```

Compilation:

```text
python -m py_compile plugins/non-profit-hermes/*.py non_profit_hermes/*.py tests/test_unified_plugin.py tests/test_event_router.py tests/test_daily_read_only.py
PASS
```

Build was run from a disposable copy so setuptools artifacts did not modify the task worktree:

```text
uv build <disposable-source-copy> --out-dir <temporary-dist>
Successfully built non_profit_hermes-1.0.0.tar.gz
Successfully built non_profit_hermes-1.0.0-py3-none-any.whl
```

The package-owned adapter source was byte-identical in the worktree, wheel, and sdist:

```text
SOURCE_SHA256=838c8621c6bd2f27d7aca6c5b86d94fc12a6b665d3d30b5d450a4205d28cd6cb
WHEEL_SHA256=838c8621c6bd2f27d7aca6c5b86d94fc12a6b665d3d30b5d450a4205d28cd6cb
SDIST_SHA256=838c8621c6bd2f27d7aca6c5b86d94fc12a6b665d3d30b5d450a4205d28cd6cb
PARITY=True
```

`git diff --check` passed.

## NPH-V1-030B2 manifest, installer, and drift behavior

`RUNTIME_PLUGIN_MANIFEST.json` is schema/version 2 with `default_mode: unified`. Its first entry is the v1.0.0 primary plugin at `plugins/non-profit-hermes`, with all seven commands and exact Git-blob SHA-256 values for `__init__.py`, `commands.py`, and `plugin.yaml`. Seven v1.0.0 compatibility entries follow in historical command order `daily`, `event`, `need`, `donation`, `report`, `task`, `inventory`, each with an explicit `runtime_plugins/...` source and exact hashes for `__init__.py` and `plugin.yaml`.

All eight source paths were verified normalized, repository-relative, and contained by the repository root. All 17 declared hashes matched `git show HEAD:<source>/<file>`, and every manifest identity/version matched its source `plugin.yaml`.

Installer behavior:

- default dry-run and apply select only `non-profit-hermes` and print `mode=unified`;
- `--mode legacy` selects only the seven compatibility directories;
- no mode selects unified and legacy together, and duplicate command exposure fails closed;
- unsafe/absolute/traversal/unnormalized sources and manifest identity/version/hash mismatches fail closed;
- dirty apply, implicit targets, and the live root without `--live` remain refused;
- atomic staging, Git-blob/CRLF handling, backup, rollback-on-failure, and declared mutable-state preservation remain intact;
- the installer performs no configuration enable/disable or removal action.

Drift behavior:

- default `--mode unified` checks one primary plugin;
- `--mode legacy` checks seven compatibility shims;
- `--mode all` audits all eight entries read-only;
- JSON includes manifest version, mode, source, role, plugin identity/version, and `read_only: true`;
- strict failures are scoped to missing, unexplained, or untested state in the selected mode;
- unsafe source values are redacted and rejected; no credential or private path is emitted.

Disposable non-live integration proof used temporary roots only:

```text
MANIFEST_V2_HASH_SOURCE_IDENTITY=PASS entries=8 files=17
DRY_RUN_DEFAULT=PASS directories=non-profit-hermes target_created=false
DRY_RUN_LEGACY=PASS directories=7 target_created=false
APPLY_UNIFIED=PASS directories=1
APPLY_LEGACY=PASS directories=7 disjoint=true
BACKUP_MUTABLE_RESTORE=PASS backups=1
ROLLBACK_ON_FAILURE=PASS known_good_restored=true
DRIFT_UNIFIED_STRICT=PASS plugins=1
DRIFT_LEGACY_STRICT=PASS plugins=7
DRIFT_ALL_AUDIT=PASS plugins=8 read_only=true
DRIFT_MUTATION_STRICT=PASS exit=1 no_writes=true
```

B2 full verification:

```text
python -m pytest -q
323 passed, 69 subtests passed in 15.04s

python -m py_compile scripts/install_runtime_plugins.py scripts/check_runtime_plugin_drift.py tests/test_runtime_plugin_*.py tests/test_legacy_plugin_shims.py tests/test_unified_plugin.py
PASS

git diff --check
PASS
```

## Scans and boundaries

The final verification scans cover:

- exact B2 nine-path change set: manifest, two tooling scripts, three focused test files, two operator/developer documents, and this report;
- no changes under canonical unified or legacy plugin source, package source, profile/distribution inputs, public `docs/`, or live/profile paths;
- no hardcoded Windows or macOS user/repository path in the plugin/package diff;
- no raw numeric Telegram source identifier in the plugin/package diff;
- no `sys.path`, subprocess, `scripts` import, dynamic reload, Google import/logic, credentials read, token path, hook, or tool registration in the unified plugin;
- no credential/token/private-ID shape added to the report;
- manifest exact fields and v1.0.0 identity.

## Compatibility state, limitations, and deferred work

- The unified v1.0.0 plugin is canonical source. Seven v1.0.0 legacy plugins remain as deprecated one-release rollback shims only.
- Unified and legacy modes expose duplicate command names by design and must never be enabled together. Migration must disable the opposite set before gateway start.
- The installer copies a selected set but intentionally does not enable, disable, or remove plugins.
- The canonical plugin source is not installed, enabled, or included in a profile distribution by these slices. Distribution wiring, clean-install acceptance, independent checking, and production migration are later gates.
- No live profile, gateway, Telegram bot, Google Sheet, Google Calendar, public site, or publication action was performed.
- No live command canary was run. This report is local/offline builder evidence, not independent checker or production acceptance.

## No-live-action statement

These slices performed source edits, offline tests, compilation, static scans, a disposable local package build, and B2 installer/drift exercises under temporary non-live roots only. They did not access nonprofit credentials, mutate Google or Calendar data, alter any Hermes profile or live plugin installation, enable or disable plugins, restart a gateway, contact Telegram, or publish the public website.
