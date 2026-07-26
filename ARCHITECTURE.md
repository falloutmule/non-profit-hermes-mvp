# Architecture — Non-Profit Hermes MVP

**Current architecture captured:** 2026-07-21

## Current deployed shape

```text
Telegram user
  -> @HnonProfitBOT
  -> separate nonprofit gateway (currently stopped)
  -> nonprofit Hermes profile
  -> openai-codex/gpt-5.6-sol
  -> seven enabled legacy command plugins
  -> scripts/telegram_intake_router.py
       |-> /daily approved-safe read-only snapshot
       |-> draft-first command routing
  -> scripts/non_profit_hermes_ops.py
       |-> Google Sheets rows + AuditLog
       `-> explicitly authorized Google Calendar events

Separate publication path
Google Sheets + Calendar
  -> scripts/sync_approved_safe_data.py
  -> reviewed approved-safe HTML/JSON under docs/
  -> separately authorized GitHub Pages publication
```

The bot identity, profile, model route, plugin enablement, and Telegram command registry were verified read-only. The gateway is stopped, so the full chain above describes the deployed design, not a currently running dispatch path.

## Runtime and profile topology

- `nonprofit` is an isolated Hermes profile with its own bot credential and model route.
- The seven nonprofit plugins are disabled in `default` and enabled in `nonprofit`.
- A separate Windows Scheduled Task launches `hermes --profile nonprofit gateway run` through a profile-local VBS launcher.
- Profile config declares API host `127.0.0.1` and port `8642`.
- The Scheduled Task launcher overrides the port to `8643`; this is the intended task-launched port.
- On 2026-07-21, no nonprofit gateway process or `8643` listener existed. The effective bind remains untested.
- Gateway state metadata incorrectly still claimed `running`, and two additional generated service/startup paths reported by status were absent. The actual Scheduled Task points to the existing launcher.

Runtime state, Scheduled Task state, port listeners, and command registration are separate facts. A `Ready` task or registered command does not prove a running gateway.

## Plugin source, discovery, and installation

Canonical source is in the repository:

```text
runtime_plugins/
  non-profit-hermes-daily/
  non-profit-hermes-need/
  non-profit-hermes-donation/
  non-profit-hermes-report/
  non-profit-hermes-task/
  non-profit-hermes-inventory/
  non-profit-hermes-event/
```

Each plugin is a thin legacy shim that registers one command and delegates to the repository router. Business and Google logic remain in `scripts/`.

Discovery/install topology:

```text
runtime_plugins/                         canonical tracked source
  -> RUNTIME_PLUGIN_MANIFEST.json        tracked file hashes and mutable patterns
  -> scripts/install_runtime_plugins.py  deliberate copy/install boundary
  -> <hermes-home>/plugins               shared installed root
  <- <nonprofit-profile>/plugins         Windows junction/reparse point
```

`scripts/check_runtime_plugin_drift.py` compares installed files against the manifest without writing. Current strict inspection returned only `EXPECTED DERIVATION` for bytecode caches and found no missing or unexplained file.

The installer is dry-run by default. On apply it verifies the manifest, stages a complete directory, preserves declared mutable files, moves an existing target to a timestamped backup, atomically replaces the target, and restores the backup when replacement fails. It does not enable plugins, configure a profile, or start a gateway.

## Command layer

The Telegram registry contains seven commands:

```text
/daily
/need
/donation
/report
/task
/inventory
/event
```

`scripts/telegram_intake_router.py` provides:

- draft-first creation for write commands;
- per-source active-draft pointers;
- command-specific follow-up routing;
- privacy classification and safe user responses;
- `/daily` approved-safe summary rendering.

`/daily` calls `daily_services()`, which requests `persist_refresh=False`, reads approved-safe source data, and builds the response in memory. It does not call the public writer or create Google records.

The six intake commands are mutation-capable when connected to live Google services. `/event` creates or updates a CalendarLog draft; actual Calendar creation is a separate, guarded, per-event promotion.

## Private data and mutation layer

`scripts/non_profit_hermes_ops.py` owns structured writes:

- Requests
- Donations
- Reports
- Tasks
- Inventory
- CalendarLog
- AuditLog

Every supported create/update path maintains the canonical header contract and writes an audit entry. Tasks and Inventory are internal-only. Automated report writes keep sensitive detail fields empty.

Google Calendar is not a general `/event` side effect. Promotion requires explicit authorization for one named draft, guard checks, authorization consumption before the external attempt, same-row event-ID persistence, and idempotence verification.

## OAuth refresh boundary

Operational loaders use `scripts/google_oauth_refresh.py` for durable refresh:

```text
load operational credential
  -> refresh in memory
  -> serialize separate candidate
  -> validate credential, scopes, identity, hash, and ACL invariants
  -> acquire exclusive refresh lock
  -> write and flush exact-byte backup
  -> atomically replace operational file
  -> verify hash/ACL and clean temporary state
  -> delete backup on success or restore it on post-swap failure
```

This is atomic/recoverable persistence with secret-free error evidence. `/daily` and sync `--dry-run` intentionally bypass durable persistence and refresh only in memory.

## Approved-safe publication layer

`scripts/sync_approved_safe_data.py` reads all relevant Sheet ranges and Calendar data, deduplicates records, applies deny-by-default gates, escapes user-controlled HTML, and writes generated static output under `docs/` only when run without `--dry-run`.

Publication gates include:

- Requests: approved privacy, approved public status, affirmative consent
- Donations: approved privacy, approved public status, affirmative public-listing permission
- Reports: approved privacy, approved public status, affirmative public-summary permission, non-empty approved summary
- Calendar: approved CalendarLog record joined to an existing Calendar event
- Board log: aggregate-only output
- Tasks and Inventory: never exported

Generation is not publication. An operator must review generated changes and obtain explicit publication authorization before commit or push. The 2026-07-21 inventory did not rerun generation parity.

## Current production versus release candidate

The current production profile remains script-based and uses seven separate legacy plugins. The local `packaging/non-profit-hermes-v1` release candidate now contains:

- importable `non_profit_hermes` package;
- one unified plugin registering all seven commands;
- secret-free installable profile distribution;
- deterministic runtime doctor;
- disposable repository-only clean-install acceptance (23/23 stages, 379 tests, 69 subtests, production untouched).

Those candidate capabilities are not yet GitHub-released or migrated into the live profile. Production migration, human Telegram canaries, and live-readonly doctor verification remain separate gates. Historical operational modules may retain user-specific paths, but the candidate publication boundary is now audited and redacted.