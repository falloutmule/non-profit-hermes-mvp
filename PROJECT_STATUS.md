# Project Status — Non-Profit Hermes MVP

**Canonical status reconciled:** 2026-07-26

Source precedence for this status is current direct runtime inspection, then current Git/GitHub, passing tests, accepted clean-install evidence, current reports, historical documentation, and finally inference. Historical reports remain evidence of what was tested at the time; they are not proof of present runtime state or standing authorization.

## Exact repository state

| Item | Current truth |
|---|---|
| Repository | `falloutmule/non-profit-hermes-mvp` |
| Production branch | `main` |
| Last inspected GitHub `main` SHA | `91143b3bacb46f799292027f1697376932b55403` |
| Packaging branch | `packaging/non-profit-hermes-v1` |
| Local release-candidate SHA | `754c2b8625653f845451b8a97186a6e23cb176dc` |
| Candidate version | `1.0.0` |
| GitHub PR/tag/release | not yet created |
| GitHub Pages source | `main /docs` |

The production SHA and packaging-branch commits are intentionally distinct. Packaging work is in progress and is not production `main`, a release, or `v1.0.0`.

## Runtime state

Verified read-only on 2026-07-21:

- Telegram bot identity: `@HnonProfitBOT`
- Hermes profile: `nonprofit`
- Model/provider route: `openai-codex/gpt-5.6-sol`
- Gateway CLI/process state: **stopped**
- Separate Scheduled Task: `Hermes_Gateway_nonprofit`, enabled and `Ready`
- Scheduled Task launcher: existing profile-local VBS launcher invoking `hermes --profile nonprofit gateway run`
- Profile config API port: `8642`
- Launcher override and intended Scheduled Task port: `8643`
- Port `8643`: not listening
- Gateway state metadata: stale `running` claim; no nonprofit process, PID file, or lock file detected
- Two additional service/startup artifacts reported by gateway status: absent; the actual Scheduled Task points to the existing launcher

Port `8642` was occupied by another process during inspection. The effective nonprofit bind to `8643` is inferred from the launcher, not runtime-verified. No gateway start, stop, or restart was performed.

## Plugins and commands

Seven canonical legacy plugin source directories exist under `runtime_plugins/`. The manifest, dry-run-by-default installer, and read-only drift checker are tracked in the repository. The installed shared plugin root and the `nonprofit` profile-local plugin junction were inspected without mutation.

- Seven plugin directories installed
- Seven plugins enabled in `nonprofit`
- All seven nonprofit plugins disabled in `default`
- Strict drift check: exit `0`
- Result: only expected `__pycache__` derivations; no missing canonical file or unexplained drift

The Telegram Bot API registry contained all seven commands:

| Command | Function | Current acceptance state |
|---|---|---|
| `/daily` | Board-safe in-memory summary | Registered; focused local read-only tests pass; current live dispatch untested |
| `/need` | Draft-first Requests intake | Registered and plugin enabled; current live dispatch untested |
| `/donation` | Draft-first Donations intake | Registered and plugin enabled; current live dispatch untested |
| `/report` | Draft-first Reports intake | Registered and plugin enabled; current live dispatch untested |
| `/task` | Draft-first internal Tasks intake | Registered and plugin enabled; current live dispatch untested |
| `/inventory` | Draft-first internal Inventory upsert | Registered and plugin enabled; current live dispatch untested |
| `/event` | Draft-first CalendarLog intake | Registered and plugin enabled; current live dispatch untested; promotion requires per-event authorization |

Registry presence proves registration, not transport or dispatch. The gateway is stopped, so current human-originated `/commands` and `/daily` canaries are untested.

Historical evidence is retained but labeled precisely: `CLEANUP_003_DAILY_READ_ONLY_REPORT.md` records a user-supplied human-originated `/daily` response dated **2026-07-12**. Earlier command reports record implementation-era live wiring and acceptance. Those are historical observations, not present runtime proof.

## Implemented repository capabilities

- Draft-first router/backend flows for all seven commands
- Google Sheets as system of record with append-only audit entries for mutations
- Per-event authorization and idempotence safeguards for Calendar promotion
- Deny-by-default approved-safe export filtering and escaped public HTML
- `/daily` approved-safe in-memory collection with no docs generation and no durable token refresh
- Canonical Sheet schema shared by write and export paths
- Atomic OAuth refresh persistence for operational loaders: in-memory refresh, separate candidate, invariant validation, lock, exact-byte backup, atomic replacement, verification, cleanup, and rollback on post-swap failure
- Seven tracked legacy plugin copies, manifest verification, deliberate installer, timestamped directory backups, failed-replacement restore, and strict read-only drift classification
- Root pytest discovery limited to `tests/` and excluding linked `worktrees/`

The `/daily` path and sync `--dry-run` intentionally refresh credentials in memory only. Operational backend loaders and an explicitly writing sync use the atomic durable-refresh boundary when persistence is needed.

## Test and package acceptance state

Accepted clean-install evidence for the release candidate:

```text
NPH-V1-060N-20260726073936
23/23 acceptance stages passed
379 tests passed, 69 subtests passed
production_touched: false
```

The package, unified plugin, secret-free profile distribution, deterministic doctor, and repository-only clean install are therefore **verified in the disposable acceptance environment**. This does not establish present production runtime health, tag/release publication, or profile migration.

## Privacy and mutation state

- Tests are fake-based and offline.
- `/daily` is read-only and does not write Google data, public files, or durable credential state.
- Intake commands can write private Sheets records and AuditLog rows when live services are used.
- Calendar creation requires separate authorization for the exact draft; prior controlled promotion is not reusable authority.
- Public sync is separate from `/daily`; generation and publication require explicit approval and review.
- No Google write, Calendar write, Telegram send, public generation/publication, gateway lifecycle action, profile/plugin edit, or Hermes update occurred during the current inventory.

## Pending release and migration gates

- Push the release-candidate branch, review it in a pull request, and pass GitHub CI.
- Merge to `main`, create annotated tag `v1.0.0`, publish the GitHub release, and reinstall release artifacts in a fresh disposable environment.
- Inventory and back up the current manual `nonprofit` profile.
- Install and verify the tagged distribution in a staging profile; migrate only user-owned private configuration.
- Obtain explicit live-cutover approval, migrate the live profile, and perform human-originated `/commands` and read-only `/daily` canaries.
- Retain rollback through the observation window.

## Untested and known limitations

- Nonprofit gateway startup and effective `8643` bind
- Current human-originated `/profile`, `/model`, `/commands`, and `/daily` canaries
- Current live `/daily` Google reads and zero-write counters
- Public-site generation parity
- Physical-device acceptance
- Operational scripts and all seven legacy plugin entrypoints contain user-specific paths and `sys.path` mutation
- Config and launcher ports differ; gateway metadata is stale
- Two status-reported generated service/startup artifacts are absent
- Installation currently reproduces plugins only; credentials, profile configuration, plugin enablement, and gateway setup remain manual

## Supersession

This file supersedes prior canonical-status claims. Historical reports remain authoritative only for their bounded, dated evidence. See [reports/README.md](reports/README.md) for the public-report policy and supersession map.