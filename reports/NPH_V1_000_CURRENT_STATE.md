# NPH-V1-000 — Current State

Captured: 2026-07-21T09:34:30-06:00

Scope: read-only inventory of Git/GitHub, repository contents, the authoritative `nonprofit` Hermes profile, installed plugins, Telegram Bot API identity/command registration, Windows launcher/Scheduled Task/API ports, default-profile isolation, and the current test baseline.

No Google write, Calendar write, public sync/publication, Telegram send, gateway lifecycle action, plugin/profile edit, Scheduled Task edit, or Hermes update was performed.

## Classification

- **verified** — directly observed in current Git, GitHub, repository, Hermes CLI, Windows state, Telegram Bot API, or executed tests.
- **inferred** — derived from verified evidence but not exercised end to end.
- **proposed** — approved target architecture, not current state.
- **untested** — not exercised because it required a forbidden mutation, a stopped runtime, a human-originated canary, or a later task.

Machine-readable detail: `reports/NPH_V1_000_CURRENT_STATE.json`.

## Packaging gate

**READY — verified.**

The offline packaging preconditions pass:

- local HEAD, local `main`, `origin/main`, and live remote `main` all equal `91143b3bacb46f799292027f1697376932b55403`;
- the assigned packaging worktree was clean before these reports;
- `completion-refresh-001` and `completion-installer-001` are not direct ancestors, but every commit is patch-equivalent to content already in `main`;
- `cleanup-007a` is a direct ancestor of `main`;
- the `nonprofit` profile credential resolves read-only to `@HnonProfitBOT` and differs from the default profile bot;
- canonical repository plugin files and installed plugin files have no unexplained drift.

Runtime acceptance remains pending because the nonprofit gateway is stopped. This does not block offline packaging, but no later task may describe the stopped runtime as live-verified.

## Git and GitHub

### Verified

- Branch: `packaging/non-profit-hermes-v1`
- HEAD: `91143b3bacb46f799292027f1697376932b55403`
- HEAD parents:
  - `f0b7240fbd34a7ab4dc0c826a995c20f71f085f3`
  - `d5a22eacdcb6af1d8c5b192698afa6ed54036bb9`
- Local `main`: `91143b3bacb46f799292027f1697376932b55403`
- `origin/main`: `91143b3bacb46f799292027f1697376932b55403`
- Live remote `refs/heads/main`: `91143b3bacb46f799292027f1697376932b55403`
- Open PRs: none.
- Merged PRs:
  - PR #1, merge commit `f0b7240fbd34a7ab4dc0c826a995c20f71f085f3`
  - PR #2, merge commit `91143b3bacb46f799292027f1697376932b55403`
- Tags: none.
- Local branches: `cleanup-005a`, `cleanup-005b`, `cleanup-006a`, `cleanup-006b-r2d`, `cleanup-007a`, `completion-installer-001`, `completion-refresh-001`, `fix/pytest-worktree-discovery`, `main`, and `packaging/non-profit-hermes-v1`.
- Remote branches: `origin/cleanup-007a`, `origin/fix/pytest-worktree-discovery`, and `origin/main`.
- Five registered worktrees remain; none was removed or modified.

### Worktree containment

`completion-refresh-001`:

- direct ancestor: no;
- `git cherry main completion-refresh-001` returned only negative markers:
  - `- 36b8298bee46d916bfb01543fb26ef102bb649aa`
  - `- e9215fb2f32ecff0f87caf4d9ff72b15e4b8b235`
- `git log --cherry-pick --right-only --no-merges --oneline main...completion-refresh-001` returned no commits.
- Conclusion: **verified fully patch-contained; no unique patch remains.**

`completion-installer-001`:

- direct ancestor: no;
- `git cherry main completion-installer-001` returned only negative markers:
  - `- d2fcbacce04c41f8b63ff3327233797aca0b80e5`
  - `- 7fa57d54499997bbd605f54d8ecdf6d096ac8519`
- `git log --cherry-pick --right-only --no-merges --oneline main...completion-installer-001` returned no commits.
- Conclusion: **verified fully patch-contained; no unique patch remains.**

`cleanup-007a`:

- direct ancestor: yes.
- Conclusion: **verified directly contained.**

## Repository inventory

### Verified current contents

- 174 tracked files.
- 39 tracked Python files.
- 17 tracked test modules.
- Router/backend/schema/sync/refresh remain script modules:
  - `scripts/telegram_intake_router.py`
  - `scripts/non_profit_hermes_ops.py`
  - `scripts/non_profit_hermes_schema.py`
  - `scripts/sync_approved_safe_data.py`
  - `scripts/google_oauth_refresh.py`
- Seven canonical legacy runtime plugin source directories exist under `runtime_plugins/`.
- Runtime reproducibility assets exist:
  - `RUNTIME_PLUGIN_MANIFEST.json`
  - `scripts/install_runtime_plugins.py`
  - `scripts/check_runtime_plugin_drift.py`
- `pytest.ini` sets `testpaths = tests` and `norecursedirs = worktrees`.
- Current `main` contains the seven plugin sources, installer, drift checker, atomic refresh implementation, pytest worktree-discovery fix, and runtime documentation.

### Verified absent from current `main`

- `pyproject.toml`
- requirements file
- `distribution.yaml`
- importable `non_profit_hermes/` package
- unified `plugins/non-profit-hermes/` plugin
- runtime doctor

### Portability findings

Verified user-specific repository paths exist in:

- `scripts/telegram_intake_router.py:27`
- `scripts/non_profit_hermes_ops.py:57`
- `scripts/sync_approved_safe_data.py:45`
- all seven `runtime_plugins/*/__init__.py` entrypoints

Verified user-specific Hermes token paths exist in:

- `scripts/non_profit_hermes_ops.py:58`
- `scripts/sync_approved_safe_data.py:48`

Verified `sys.path` mutation exists in the router, ops, sync, OAuth live runner, and all seven legacy plugin entrypoints. No direct `import scripts` / `from scripts...` package imports were found; modules instead insert directories and import sibling names.

### Generated and legacy artifacts

Verified tracked state includes:

- generated/public site output under `docs/` and `docs/data/`;
- historical root-level site/data copies;
- six proof directories containing saved HTML, headers, and screenshots;
- `current-needs.md.orig` and `index.md.orig`.

**Untested:** public-generation parity. `scripts/sync_approved_safe_data.py` was not run because that path can read production Google data and write generated public files. Live mutation/publication was forbidden.

## Hermes runtime

### Installed Hermes and profile

Verified:

- Hermes Agent `v0.18.2` (`2026.7.7.2`), upstream `d604141d`.
- Install method: Git.
- No update was performed.
- Profile: `nonprofit`.
- Model/provider: `gpt-5.6-sol` / `openai-codex`.
- Gateway CLI state: stopped.

### Bot identity and isolation

Verified by secret-safe Telegram Bot API reads:

- nonprofit bot: `@HnonProfitBOT` (`Hermes Non-Profit`, bot ID `8869177857`);
- nonprofit token SHA-256 prefix: `06e2f89b098d`;
- default bot: `@HermesplzBot` (bot ID `8781427724`);
- default token SHA-256 prefix: `9f22e48b1bd5`;
- fingerprints are distinct;
- all seven nonprofit user plugins are disabled in `default` and enabled in `nonprofit`.

No token value or raw private chat ID is included in either report.

### Plugin discovery, install state, and parity

Verified:

- shared installed root: `<hermes-home>/plugins`;
- profile-local path: `<hermes-home>/profiles/nonprofit/plugins`;
- the profile-local path is a Windows reparse point/junction resolving to the shared root;
- seven nonprofit plugin directories are installed;
- all seven are enabled for `nonprofit`;
- strict drift check exited 0;
- every plugin classified `EXPECTED DERIVATION` because only `__pycache__` files are extra;
- no canonical file is missing and no unexplained drift exists.

### Telegram command registry

Verified by `getMyCommands`:

- `/daily`
- `/donation`
- `/event`
- `/inventory`
- `/need`
- `/report`
- `/task`

The registry contains all seven commands. This is registration evidence only; it does not prove live dispatch while the gateway is stopped.

### Gateway launcher and Scheduled Task

Verified:

- Scheduled Task: `Hermes_Gateway_nonprofit`.
- State: `Ready`; enabled; at-logon trigger.
- Last run: `2026-07-20T03:45:28-06:00`; result `0`.
- Actual task command: `wscript.exe <nonprofit-home>/startup/launch_nonprofit_gateway.vbs`.
- Start directory: the nonprofit profile home.
- Launcher exists and SHA-256 is `ae9bc85e3a5fe83760b78df038065dc2f85b0dedfda014bef9f2122b9c9eb010`.
- Launcher invokes `hermes --profile nonprofit gateway run` and sets `API_SERVER_PORT=8643`.
- No nonprofit gateway process, PID file, or lock file is currently detected.
- `gateway_state.json` still claims `running` and is stale.
- Last recorded lifecycle event was `gateway.start`, PID `29832`, at `2026-07-20T14:40:15.336005+00:00`.
- `hermes gateway status --deep --full` additionally reports two generated paths that are absent:
  - `<nonprofit-home>/gateway-service/Hermes_Gateway_nonprofit.cmd`
  - `<user-startup>/Hermes_Gateway_nonprofit.vbs`

The actual Scheduled Task points to the existing `startup/launch_nonprofit_gateway.vbs`; the two status-reported service/startup artifacts are separate missing artifacts.

### API port

Verified:

- profile config: API server enabled, host `127.0.0.1`, port `8642`;
- Scheduled Task launcher override: `8643`;
- `127.0.0.1:8642` is currently listening under PID `45040`;
- no listener exists on `8643`.

**Inferred:** when the current Scheduled Task starts the nonprofit gateway, its effective port should be `8643` because the launcher overrides the config value.

**Untested:** the actual nonprofit bind. Start/restart was forbidden.

### `/daily`

Verified in source and focused tests:

- the plugin delegates to the repository router through a hardcoded scripts path;
- `run_daily_summary()` builds an approved-safe in-memory snapshot;
- `daily_services()` uses `creds(persist_refresh=False)`, so an expired credential refresh remains in memory;
- the daily path does not call the public-site writer;
- `python -m pytest -q tests/test_daily_read_only.py` returned `5 passed in 0.44s`.

**Untested live:** no human-originated `/daily` was sent because Telegram sends were forbidden and the nonprofit gateway is stopped. Zero-write behavior is builder-verified with fakes, not live-verified in this inventory.

## Test baseline

Verified:

```text
python -m pytest -q tests/test_daily_read_only.py
5 passed in 0.44s
```

```text
python -m pytest -q
235 passed, 64 subtests passed in 6.48s
```

```text
python scripts/install_runtime_plugins.py --dry-run
DRY-RUN: manifest verified; no files will be written.
would install seven plugins
```

```text
python scripts/check_runtime_plugin_drift.py --installed-root <hermes-home>/plugins --json --strict
exit 0; all seven EXPECTED DERIVATION; no missing or unexplained files
```

## Proposed target state

The approved later-task target remains **proposed**, not implemented:

- portable importable `non_profit_hermes` package;
- one unified plugin registering seven commands;
- secret-free installable nonprofit profile distribution using the installed Hermes schema;
- deterministic runtime doctor;
- clean-install, update, rollback, checker, and production migration acceptance.

## Untested

- live nonprofit gateway startup and effective `8643` bind;
- human-originated `/profile`, `/model`, `/commands`, and `/daily` canaries;
- current live `/daily` Google reads and zero-write counters;
- public-site generation parity;
- physical-device acceptance.

## Known limitations

- Production modules and all seven legacy plugins are not portable because they contain user-specific paths and `sys.path` mutation.
- Packaging, unified plugin, profile distribution, and doctor artifacts do not exist yet.
- Config and launcher express different API ports; the launcher appears intended to avoid the occupied config port.
- Gateway state metadata is stale and two status-reported service/startup artifacts are missing.
- Telegram command registration exists, but stopped-runtime dispatch remains unverified.
- Generated public-site parity was intentionally not rerun.

## Exact commands

Paths shown with `<user-home>` / `<hermes-home>` are redacted path equivalents; no secret value is substituted.

```text
git fetch origin main --prune
git status --porcelain=v2 --branch
git rev-parse HEAD
git rev-parse main
git rev-parse origin/main
git ls-remote origin refs/heads/main
git worktree list --porcelain
git branch --all --verbose --no-abbrev
git tag --list --format='%(refname:short) %(objectname)'
gh pr list --state open --json number,title,headRefName,baseRefName,isDraft,url
gh pr list --state merged --limit 100 --json number,title,headRefName,baseRefName,mergedAt,mergeCommit,url
git merge-base --is-ancestor completion-refresh-001 main
git merge-base --is-ancestor completion-installer-001 main
git merge-base --is-ancestor cleanup-007a main
git cherry main completion-refresh-001
git cherry main completion-installer-001
git log --cherry-pick --right-only --no-merges --oneline main...completion-refresh-001
git log --cherry-pick --right-only --no-merges --oneline main...completion-installer-001
git ls-files
hermes --version
hermes profile show nonprofit
hermes -p nonprofit status
hermes -p nonprofit gateway status --deep --full
hermes -p nonprofit plugins list --json
hermes -p default plugins list --json
schtasks.exe /Query /TN "\\Hermes_Gateway_nonprofit" /V /FO LIST
python scripts/check_runtime_plugin_drift.py --installed-root <hermes-home>/plugins --json --strict
python scripts/install_runtime_plugins.py --dry-run
python -m pytest -q tests/test_daily_read_only.py
python -m pytest -q
date -Iseconds
```

Secret-safe inline Python helpers were also executed for three bounded purposes:

1. parse only the locally stored Telegram token, call `getMe` / `getMyCommands`, and emit only allowlisted bot identity, command names/descriptions, and a 12-hex SHA-256 prefix;
2. compare only the `default` and `nonprofit` bot identities/fingerprint prefixes;
3. parse the nonprofit config and emit only allowlisted model/provider/API host/port/enablement fields.

The helpers emitted no token, API key, authorization header, OAuth payload, Google private record, or raw private chat ID.

## Evidence paths

- Repository evidence: `$WORKTREE` (redacted as `<user-home>/non-profit-hermes-mvp/worktrees/nph-v1-package-001`).
- Nonprofit profile metadata: `$NONPROFIT_HOME` (redacted as `<hermes-home>/profiles/nonprofit`).
- Installed plugin metadata: `$PLUGIN_ROOT` (redacted as `<hermes-home>/plugins`).
- Launcher metadata: `$NONPROFIT_LAUNCHER` (redacted as `<hermes-home>/profiles/nonprofit/startup/launch_nonprofit_gateway.vbs`).
- Reports:
  - `reports/NPH_V1_000_CURRENT_STATE.md`
  - `reports/NPH_V1_000_CURRENT_STATE.json`

## Closeout verification

Verified before staging:

- `python -m json.tool reports/NPH_V1_000_CURRENT_STATE.json > /dev/null` exited 0;
- secret scan found no Telegram token, OpenAI-style key, bearer authorization value, OAuth token/client-secret value, private-key block, or configured private chat/user ID literal;
- `git diff --check` exited 0;
- `git status --short` listed exactly the two approved untracked report paths.

Commit, exact-parent, clean-status, and report-hash verification are recorded in the task handoff because a report cannot safely contain its own final Git blob/hash state before the commit exists.
