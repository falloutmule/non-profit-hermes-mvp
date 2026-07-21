# Operations — Non-Profit Hermes MVP

**Current operating boundary captured:** 2026-07-21

## Start with current state

The authoritative runtime is the `nonprofit` Hermes profile for `@HnonProfitBOT`, routed to `openai-codex/gpt-5.6-sol`. The nonprofit gateway is currently **stopped**.

A separate Windows Scheduled Task exists and is enabled, but `Ready` is not proof of a running gateway. The profile config specifies port `8642`; the Scheduled Task launcher overrides to the intended port `8643`. On 2026-07-21, `8643` was not listening, gateway metadata was stale, and no nonprofit process, PID file, or lock file was detected.

Do not claim command dispatch, start/restart the gateway, or alter the Scheduled Task without a separately authorized runtime task and rollback plan.

## Safe repository verification

Run from the repository root:

```bash
python -m pytest -q
python -m pytest -q tests/test_daily_read_only.py
python scripts/install_runtime_plugins.py --dry-run
git diff --check
```

Current expected baseline is `235 passed, 64 subtests passed`; the focused `/daily` suite has 5 tests. Pytest is fake-based and offline.

## Plugin installation and drift

Canonical plugin sources are under `runtime_plugins/`, with hashes in `RUNTIME_PLUGIN_MANIFEST.json`.

Dry-run manifest verification performs no writes:

```bash
python scripts/install_runtime_plugins.py --dry-run
```

Apply to an explicit disposable or selected plugin root:

```bash
python scripts/install_runtime_plugins.py --apply --target-root <plugin-root>
```

The live shared Hermes plugin root is refused unless `--live` is also supplied. Do not use `--allow-dirty-git` except for a deliberate, documented temporary proof.

On apply, the installer:

1. verifies the manifest;
2. stages canonical files without bytecode;
3. preserves declared mutable files;
4. moves an existing plugin directory to `<plugin-root>/.cleanup_004_backups/<plugin>.<UTC timestamp>`;
5. atomically replaces the target;
6. restores the backup if staged replacement fails.

The installer does not configure credentials, enable plugins for `nonprofit`, create the profile-local junction, or start the gateway. Those remain manual operations. Preserve backups until verification and an explicit retention decision.

Read-only drift check:

```bash
python scripts/check_runtime_plugin_drift.py --installed-root <plugin-root> --json --strict
```

Strict mode fails for missing, unexplained, or untested state. On 2026-07-21, the installed shared root passed with only expected bytecode derivations.

## Gateway acceptance sequence

After a separately authorized startup or restart, verify each layer rather than inferring health:

1. exact `nonprofit` profile and expected model/provider;
2. exact `@HnonProfitBOT` identity using a secret-safe read;
3. one nonprofit gateway process;
4. effective `127.0.0.1:8643` listener when launched by the Scheduled Task;
5. seven enabled nonprofit plugins and no nonprofit plugins enabled in `default`;
6. all seven Telegram registry entries;
7. human-originated `/commands` and `/daily` canaries;
8. `/daily` zero-write evidence;
9. no public-file generation or publication.

These checks are currently pending because no gateway lifecycle action was authorized. Historical human-originated `/daily` evidence dated 2026-07-12 is retained in `CLEANUP_003_DAILY_READ_ONLY_REPORT.md` but does not replace a current canary.

## Command behavior

- `/daily` reads approved-safe Sheets/Calendar data and builds the summary in memory. It performs no Google mutation, public-file generation, or durable token refresh.
- `/need`, `/donation`, `/report`, `/task`, and `/inventory` are draft-first mutation paths when live Google services are connected. Every supported write adds an AuditLog entry.
- `/event` writes a CalendarLog draft. It does not grant Calendar creation authority.
- Calendar promotion requires a fresh authorization for the exact draft, preflight and guard checks, one consumed attempt, same-row event-ID persistence, and idempotence/privacy verification.

The Telegram registry proves command registration only. While the gateway is stopped, no command should be described as currently live-dispatch verified.

## OAuth refresh behavior

Operational loaders persist an expired credential through the atomic refresh boundary:

- refresh in memory;
- write and validate a separate candidate;
- lock the operational file;
- create and flush an exact-byte rollback backup;
- atomically replace and verify;
- delete temporary state and backup on success;
- restore exact bytes and ACL on handled post-replacement failure.

Errors and evidence use status codes and hashes, not credential values. `/daily` and sync `--dry-run` intentionally request in-memory refresh only and do not persist a token.

## Approved-safe generation and publication

Inspect live source data without filesystem writes:

```bash
python scripts/sync_approved_safe_data.py --dry-run
```

Generate local public output only with separate authorization:

```bash
python scripts/sync_approved_safe_data.py
```

Generation writes `docs/`; it does not authorize commit, push, or publication. Required sequence:

1. verify the exact authorization and data boundary;
2. run generation;
3. inspect all changed HTML/JSON for approved-safe content and escaped values;
4. verify only `docs/` generated outputs changed;
5. obtain human approval for the exact public diff;
6. commit/push only under separate publication authorization;
7. verify canonical GitHub Pages URLs.

The 2026-07-21 inventory did not rerun public-generation parity and did not publish anything.

## Explicit live-write warnings

These paths can mutate production data and are not offline tests:

```bash
python scripts/non_profit_hermes_ops.py --test-write
python scripts/telegram_intake_router.py --test
```

Do not run them without deliberate live-service authorization. Never create a Calendar event without authorization for that event. Never backfill approval flags automatically.

## Failure and rollback boundary

If plugin install verification fails, stop the gateway activation path, inspect the timestamped backup, and restore the prior plugin directory before retrying. If bot/profile/model/port identity differs, or duplicate/missing commands appear, stop and preserve evidence rather than continuing. A repository rollback does not by itself restore runtime plugins, profile state, or credentials; each state owner needs its own verified rollback.
