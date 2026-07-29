# Non-Profit Hermes MVP

Non-Profit Hermes is a Telegram-first operations assistant for a small nonprofit, mutual-aid group, or volunteer-run charity. It turns conversational intake into structured Google Sheets records, uses Google Calendar only for explicitly authorized dated commitments, and can generate a human-reviewed approved-safe snapshot for GitHub Pages.

Release-candidate truth captured: **2026-07-26**.

- Production GitHub branch: `main`
- Last inspected GitHub `main` SHA: `91143b3bacb46f799292027f1697376932b55403`
- Release-candidate branch: `packaging/non-profit-hermes-v1`
- Release-candidate SHA: `754c2b8625653f845451b8a97186a6e23cb176dc`
- Candidate version: `1.0.0` — local-only; not yet pushed, merged, tagged, or released
- Telegram identity/profile/runtime statements below are historical 2026-07-21 inventory evidence; they are not current live proof.

The release candidate contains the portable Python package, canonical unified plugin, supported root-level Hermes profile distribution, and deterministic runtime doctor. Clean-install acceptance passed in a disposable environment: 23/23 stages, 379 tests, and 69 subtests, with `production_touched: false`. An actual production live-readonly doctor, profile migration, human Telegram canaries, GitHub release/tag, and published-release install verification remain downstream gates. Source availability and clean-install acceptance are not evidence that the profile is installed or live.

## Canonical documentation

- [Project status](PROJECT_STATUS.md) — current Git, runtime, command, test, and limitation state
- [Architecture](ARCHITECTURE.md) — components, runtime topology, data flow, and trust boundaries
- [Operations](OPERATIONS.md) — current installation, verification, gateway, command, and publication procedures
- [Development](DEVELOPMENT.md) — repository layout, test commands, and development constraints
- [Security and privacy](SECURITY_AND_PRIVACY.md) — private/public boundaries and mutation safeguards
- [Reports index and supersession map](reports/README.md) — current evidence versus historical reports
- [Cleanup milestone index](CLEANUP_MILESTONE_INDEX.md) — milestone history and current authority boundary
- [Documentation reconciliation](reports/NPH_V1_DOCUMENTATION_RECONCILIATION.md) — historical documentation correction record
- [v1.0.0 release-candidate notes](RELEASE_NOTES_v1.0.0.md) — release scope, verification, installation, and known production limits

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

The release candidate unified plugin registers these seven commands. The live legacy-registry observations below are historical 2026-07-21 evidence, not current packaged-profile proof:

| Command | Purpose | Release-candidate / historical state |
|---|---|---|
| `/daily` | Board-safe operations summary | Unified plugin registered in offline acceptance; historical legacy registry observed; current live dispatch untested |
| `/need` | Draft-first request intake | Unified plugin registered in offline acceptance; historical legacy registry observed |
| `/donation` | Draft-first donation intake | Unified plugin registered in offline acceptance; historical legacy registry observed |
| `/report` | Draft-first activity report intake | Unified plugin registered in offline acceptance; historical legacy registry observed |
| `/task` | Draft-first internal task intake | Unified plugin registered in offline acceptance; historical legacy registry observed |
| `/inventory` | Draft-first inventory upsert | Unified plugin registered in offline acceptance; historical legacy registry observed |
| `/event` | Draft-first CalendarLog intake | Unified plugin registered in offline acceptance; Calendar promotion remains per-event authorized |

Current human-originated `/commands` and `/daily` canaries remain untested until the separately authorized live migration.

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

Hermes Agent `0.18.2` or newer is required. Non-Profit Hermes v1.0.0 supports Python 3.11–3.13. Python 3.14 is not supported because Hermes Agent 0.18.2 requires Python <3.14. The Python package and the Hermes profile distribution are separate installs. A profile install does not install the Python package, configure credentials, or start the gateway.

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

## Runtime doctor

After installing the package and profile, run the deterministic offline checks before any gateway start:

```bash
python -m non_profit_hermes.doctor --profile nonprofit --offline --strict
nonprofit-hermes doctor --profile nonprofit --offline --strict
```

The two entry points are equivalent. Human output is the default; add `--json` for machine-readable, redacted evidence. Exit codes are `0` healthy, `1` warning/partial, `2` configuration failure, `3` runtime failure, and `4` privacy/integrity failure. Strict mode promotes warnings to configuration failure.

`--live-readonly` is a later operational gate. It reads gateway process/task/listener state, performs Telegram `getMe`, performs one minimal Sheets read and one minimal Calendar read without credential refresh, and checks local and optionally published approved-safe markers. It never starts/stops the gateway, sends Telegram messages, mutates Google, regenerates public files, or publishes. Configure the expected public bot username through `NON_PROFIT_HERMES_EXPECTED_BOT_USERNAME`; configure local and published approved-safe checks with `NON_PROFIT_HERMES_PUBLIC_DIR` and optional HTTPS `NON_PROFIT_HERMES_PUBLIC_SITE_URL`. Do not treat source/fake verification as a production PASS.

## Development and tests

Prerequisites include Python 3.11–3.13, Git, Hermes Agent 0.18.2+, and the project dependencies declared in `pyproject.toml`. The root `distribution.yaml`, `SOUL.md`, `config.yaml`, bundled skill, and unified plugin form the installable profile payload. The runtime doctor is installed by the Python package.

Offline verification:

```bash
python -m pytest -q
python -m py_compile scripts/*.py tests/*.py
git diff --check
```

Current accepted clean-install baseline:

```text
23/23 acceptance stages passed
379 tests passed, 69 subtests passed
production_touched: false
```

`python -m pytest` uses fakes and does not make live Google calls. Explicit operational modes such as `scripts/non_profit_hermes_ops.py --test-write` can mutate live data and must not be run without deliberate authorization. The generated/public `docs/` tree is source-controlled output and must not be hand-edited.

## Known limitations

- The nonprofit gateway is stopped; current live dispatch and human canaries are unverified.
- Runtime doctor source and fake-backed offline/live-readonly tests pass, but an actual production `--live-readonly --strict` run remains pending.
- Hermes records local-source provenance in the installed `distribution.yaml`; operators should avoid publishing installed profile metadata.
- Installer preflight failures leave the prior profile untouched, but the current Hermes installer does not provide a mid-copy transactional rollback API. Exact rollback uses Git checkout plus reinstall, with user-owned state backed up and verified first.
- The deprecated seven-plugin compatibility set remains for one release and must never be enabled alongside the unified plugin.
- Config port `8642` differs from launcher override `8643`; runtime metadata is stale and two status-reported generated launcher/service paths are absent.
- Public-site generation parity was intentionally not rerun during this packaging task.
- Production migration, published tag verification, live canaries, and physical-device acceptance remain pending later authorized work.

## License

MIT.