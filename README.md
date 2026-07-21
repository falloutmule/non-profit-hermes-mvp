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

The packaging branch now contains the portable Python package, canonical unified plugin, and a supported root-level Hermes profile distribution. Runtime doctor, clean-machine acceptance, production migration, and the published `v1.0.0` tag remain downstream gates. Source availability is not evidence that the profile is installed or live.

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
  -> one unified seven-command plugin after an authorized migration
  -> scripts/telegram_intake_router.py
  -> scripts/non_profit_hermes_ops.py
  -> Google Sheets / Google Calendar

Approved-safe publication (separate, explicit workflow)
  Google Sheets / Google Calendar
  -> scripts/sync_approved_safe_data.py
  -> generated docs/ HTML and JSON
  -> human review and separately authorized GitHub Pages publication
```

The canonical source plugin is `plugins/non-profit-hermes/`. The seven entries under `runtime_plugins/` are deprecated compatibility shims retained for one release as a deterministic rollback set. `config.yaml` enables the unified plugin and disables all seven shims for a fresh distribution install; it does not alter an existing production profile until an authorized install or migration is performed.

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

## Package and profile installation

Hermes Agent `0.18.2` or newer and Python `3.11` or newer are required. The Python package and the Hermes profile distribution are separate installs. A profile install does not install the Python package, configure credentials, or start the gateway.

Local checkout:

```bash
python -m pip install .
hermes profile install . --name nonprofit
hermes profile info nonprofit
```

Published Git source:

```bash
python -m pip install "git+https://github.com/falloutmule/non-profit-hermes-mvp.git@v1.0.0"
hermes profile install https://github.com/falloutmule/non-profit-hermes-mvp.git --name nonprofit
hermes profile info nonprofit
```

The tagged Python-package command is usable only after the `v1.0.0` tag is published. The Git profile command installs the current repository default branch; use an inspected local checkout when an exact rollback revision is required. Existing-profile collisions fail unless `--force` is supplied. Review [OPERATIONS.md](OPERATIONS.md) before forcing, configuring credentials, starting a gateway, updating, rolling back, deleting a profile, or touching live Google/Calendar/publication paths.

## Development and tests

Prerequisites include Python 3.11+, Git, Hermes Agent 0.18.2+, and the project dependencies declared in `pyproject.toml`. The root `distribution.yaml`, `SOUL.md`, `config.yaml`, bundled skill, and unified plugin form the installable profile payload. Runtime doctor remains downstream work.

Offline verification:

```bash
python -m pytest -q
python -m py_compile scripts/*.py tests/*.py
git diff --check
```

Current verified full-suite baseline:

```text
335 passed, 69 subtests passed
```

`python -m pytest` uses fakes and does not make live Google calls. Explicit operational modes such as `scripts/non_profit_hermes_ops.py --test-write` can mutate live data and must not be run without deliberate authorization. The generated/public `docs/` tree is source-controlled output and must not be hand-edited.

## Known limitations

- The nonprofit gateway is stopped; current live dispatch and human canaries are unverified.
- Runtime doctor is a downstream work item, so install verification is currently the documented manual sequence.
- Hermes records local-source provenance in the installed `distribution.yaml`; operators should avoid publishing installed profile metadata.
- Installer preflight failures leave the prior profile untouched, but the current Hermes installer does not provide a mid-copy transactional rollback API. Exact rollback uses Git checkout plus reinstall, with user-owned state backed up and verified first.
- The deprecated seven-plugin compatibility set remains for one release and must never be enabled alongside the unified plugin.
- Config port `8642` differs from launcher override `8643`; runtime metadata is stale and two status-reported generated launcher/service paths are absent.
- Public-site generation parity was intentionally not rerun during this packaging task.
- Clean-machine acceptance, production migration, published tag verification, live canaries, and physical-device acceptance remain pending later authorized work.

## License

MIT.