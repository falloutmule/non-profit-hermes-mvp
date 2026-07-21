# Non-Profit Hermes MVP

Non-Profit Hermes is a Telegram-first operations assistant for a small nonprofit, mutual-aid group, or volunteer-run charity. It turns conversational intake into structured Google Sheets records, uses Google Calendar only for explicitly authorized dated commitments, and can generate a human-reviewed approved-safe snapshot for GitHub Pages.

Current truth captured: **2026-07-21**.

- Production GitHub branch: `main`
- Production GitHub `main` SHA: `91143b3bacb46f799292027f1697376932b55403`
- Public site: <https://falloutmule.github.io/non-profit-hermes-mvp/> (generated from `main /docs`; not regenerated in the current inventory)
- Packaging branch evidence base: `2276aa8f04b787e66d9eefd382fb32912660c7bb`
- Telegram identity verified read-only: `@HnonProfitBOT`
- Hermes profile: `nonprofit`
- Model: `openai-codex/gpt-5.6-sol`
- Current runtime state: **gateway stopped**

The packaging branch is work in progress. The portable Python package, unified plugin, installable profile distribution, runtime doctor, clean-install acceptance, and `v1.0.0` release described in the packaging plan are **proposed and not implemented yet**.

## Canonical documentation

- [Project status](PROJECT_STATUS.md) — current Git, runtime, command, test, and limitation state
- [Architecture](ARCHITECTURE.md) — components, runtime topology, data flow, and trust boundaries
- [Operations](OPERATIONS.md) — current installation, verification, gateway, command, and publication procedures
- [Development](DEVELOPMENT.md) — repository layout, test commands, and development constraints
- [Security and privacy](SECURITY_AND_PRIVACY.md) — private/public boundaries and mutation safeguards
- [Reports index and supersession map](reports/README.md) — current evidence versus historical reports
- [Cleanup milestone index](CLEANUP_MILESTONE_INDEX.md) — milestone history and current authority boundary
- [Current-state evidence](reports/NPH_V1_000_CURRENT_STATE.md) — read-only inventory captured 2026-07-21
- [Documentation reconciliation](reports/NPH_V1_DOCUMENTATION_RECONCILIATION.md) — claims corrected by this documentation pass

## Current architecture

```text
Telegram
  -> separate nonprofit Hermes gateway and nonprofit profile
  -> seven enabled legacy command plugins
  -> scripts/telegram_intake_router.py
  -> scripts/non_profit_hermes_ops.py
  -> Google Sheets / Google Calendar

Approved-safe publication (separate, explicit workflow)
  Google Sheets / Google Calendar
  -> scripts/sync_approved_safe_data.py
  -> generated docs/ HTML and JSON
  -> human review and separately authorized GitHub Pages publication
```

The seven canonical plugin copies are tracked under `runtime_plugins/`, described by `RUNTIME_PLUGIN_MANIFEST.json`, installed with `scripts/install_runtime_plugins.py`, and checked read-only with `scripts/check_runtime_plugin_drift.py`. The installed profile-local plugin path is a Windows junction to the shared Hermes plugin root. Current strict drift inspection passed: only expected `__pycache__` derivations were present.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the complete topology.

## Commands

| Command | Purpose | Current verified state |
|---|---|---|
| `/daily` | Board-safe operations summary | Registered; local read-only path tested; current live dispatch untested while gateway is stopped |
| `/need` | Draft-first request intake | Registered; legacy plugin enabled |
| `/donation` | Draft-first donation intake | Registered; legacy plugin enabled |
| `/report` | Draft-first activity report intake | Registered; legacy plugin enabled |
| `/task` | Draft-first internal task intake | Registered; legacy plugin enabled |
| `/inventory` | Draft-first inventory upsert | Registered; legacy plugin enabled |
| `/event` | Draft-first CalendarLog intake | Registered; legacy plugin enabled; Calendar promotion remains per-event authorized |

The Telegram Bot API command registry and bot identity were verified read-only on 2026-07-21. Registry presence does not prove current command dispatch because the nonprofit gateway is stopped. Historical evidence in `CLEANUP_003_DAILY_READ_ONLY_REPORT.md` records a human-originated `/daily` response dated **2026-07-12**; it is historical acceptance, not present runtime proof. Current human-originated `/commands` and `/daily` canaries remain untested.

## Privacy and public boundary

Google Sheets is the private system of record. Public output is deny-by-default.

- Requests require approved privacy, public status, and affirmative consent.
- Donations require approved privacy, public status, and affirmative listing permission.
- Reports require approved privacy, public status, affirmative summary permission, and an approved public summary.
- Tasks and inventory are internal-only.
- Calendar creation requires separate authorization for the exact event.
- `/daily` builds an approved-safe snapshot in memory and does not generate public files.
- Public sync and publication are separate actions; generated `docs/` content must be reviewed and explicitly authorized before commit or push.

Never put credentials, OAuth payloads, raw private chat identifiers, private Google records, sensitive locations, or personal crisis details in this repository or the public site. See [SECURITY_AND_PRIVACY.md](SECURITY_AND_PRIVACY.md).

## Current installation and operation

This repository can reproduce the **seven legacy runtime plugins**, but it cannot yet install a complete Hermes profile from Git.

Dry-run manifest verification (no writes):

```bash
python scripts/install_runtime_plugins.py --dry-run
```

Apply to an explicit non-live or disposable plugin root:

```bash
python scripts/install_runtime_plugins.py --apply --target-root <plugin-root>
```

Writing to the live shared Hermes plugin root additionally requires `--live`. Installation does not configure credentials, enable plugins for a profile, or start the gateway; those remain manual operator steps. The installer verifies tracked manifest hashes, stages each directory, preserves declared mutable files, moves an existing directory to a timestamped backup, atomically replaces it, and restores the backup if replacement fails.

The nonprofit gateway has a separate Windows Scheduled Task launcher. Profile config says port `8642`; the launcher intentionally overrides to `8643`. On 2026-07-21, `8642` was occupied by another process, `8643` was not listening, and nonprofit gateway metadata was stale. Do not treat the configured or intended port as a live binding until an authorized startup is verified.

See [OPERATIONS.md](OPERATIONS.md) before any live-root, gateway, Google, Calendar, or publication action.

## Development and tests

Prerequisites currently include Python 3.11+, Google authentication libraries, the Google API client, pytest, Git, and Hermes Agent. There is no `requirements.txt`, `pyproject.toml`, profile distribution, unified plugin, or runtime doctor yet.

Offline verification:

```bash
python -m pytest -q
python -m py_compile scripts/*.py tests/*.py
git diff --check
```

Current verified full-suite baseline:

```text
235 passed, 64 subtests passed
```

`python -m pytest` uses fakes and does not make live Google calls. Explicit operational modes such as `scripts/non_profit_hermes_ops.py --test-write` can mutate live data and must not be run without deliberate authorization. The generated/public `docs/` tree is source-controlled output and must not be hand-edited.

## Known limitations

- The nonprofit gateway is stopped; current live dispatch and human canaries are unverified.
- Operational modules and all seven legacy plugin entrypoints contain user-specific path assumptions and `sys.path` mutation.
- Dependencies are not packaged or pinned.
- Seven separate legacy plugins remain; no unified plugin exists.
- No installable profile distribution or runtime doctor exists.
- Config port `8642` differs from launcher override `8643`; runtime metadata is stale and two status-reported generated launcher/service paths are absent.
- Public-site generation parity was intentionally not rerun during the current read-only inventory.
- Clean-install, update, rollback, production migration, and physical-device acceptance are pending later authorized work.

## License

MIT.