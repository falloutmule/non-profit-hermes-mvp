# Unified Non-Profit Hermes Plugin Report

## Scope

NPH-V1-030A freezes the canonical unified plugin interface at `plugins/non-profit-hermes` without installing, enabling, or invoking it in a live Hermes profile. The plugin registers only `/daily`, `/need`, `/donation`, `/report`, `/task`, `/inventory`, and `/event`, and delegates every handler through `non_profit_hermes.router.run_plugin_command(name, raw_args)`.

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

Required focused lane:

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

## Full verification

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

## Scans and boundaries

The final verification scans cover:

- exact eight-path allowlist for this slice;
- no changes under legacy runtime plugins, runtime manifest/installers, profile/distribution inputs, public `docs/`, or live/profile paths;
- no hardcoded Windows or macOS user/repository path in the plugin/package diff;
- no raw numeric Telegram source identifier in the plugin/package diff;
- no `sys.path`, subprocess, `scripts` import, dynamic reload, Google import/logic, credentials read, token path, hook, or tool registration in the unified plugin;
- no credential/token/private-ID shape added to the report;
- manifest exact fields and v1.0.0 identity.

## Limitations and deferred work

- Seven legacy command plugins remain unchanged. Their compatibility migration is NPH-V1-030B.
- The canonical plugin source is not installed, enabled, or included in a profile distribution by this task. Distribution wiring and clean-install acceptance are later gates.
- No live profile, gateway, Telegram bot, Google Sheet, Google Calendar, public site, or publication action was performed.
- No live command canary was run. This report is local/offline builder evidence, not independent checker or production acceptance.

## No-live-action statement

This task performed source edits, offline tests, compilation, static scans, and a disposable local package build only. It did not access nonprofit credentials, mutate Google or Calendar data, alter any Hermes profile or plugin installation, restart a gateway, contact Telegram, or publish the public website.
