# Non-Profit Hermes v1.0.0 Profile Distribution Report

## Goal

Package the repository as a sanitized, supported Hermes profile distribution without changing the Python package, unified plugin source, generated public site, installed profiles, gateways, Telegram, Google services, Calendar, or publication state.

The authored root-level payload is:

- `distribution.yaml` — profile name `nonprofit`, distribution version `1.0.0`, Hermes requirement `>=0.18.2`, environment-variable declarations, and exact ownership list;
- `SOUL.md` — sanitized nonprofit mission, privacy classes, seven commands, draft/approval gates, read-only `/daily`, one-shot Calendar authorization, and publication boundary;
- `config.yaml` — `openai-codex/gpt-5.6-sol`, compression, PII/secret redaction, unified plugin enabled, and all seven legacy shims disabled;
- `skills/non-profit-hermes/SKILL.md` — bundled safe seven-command operating workflow;
- `plugins/non-profit-hermes/` — the existing unified v1.0.0 profile-local plugin, copied through explicit distribution ownership.

The Python package is a separate prerequisite because the supported profile manifest has no dependency-install field. Profile installation does not install the Python package, configure credentials, or start the gateway.

## RED

Strict TDD introduced `tests/test_profile_distribution.py` before the distribution assets and lifecycle documentation were complete. The focused documentation test was run as:

```bash
python -m pytest -q tests/test_profile_distribution.py::test_documentation_covers_supported_distribution_lifecycle_without_live_claims
```

It failed for the expected missing behavior: `reports/v1.0.0/PROFILE_DISTRIBUTION_REPORT.md` did not exist. Earlier distribution tests likewise drove the manifest, safe config, SOUL, bundled skill, ignore rules, isolated install/update/force/collision behavior, plugin registration, preservation boundaries, compatibility preflight, and secret/private-path scans.

## GREEN

The minimal documentation slice added this report and supported lifecycle guidance to `README.md`, `OPERATIONS.md`, and `DEVELOPMENT.md`. The focused RED test then passed (`1 passed`) before the broader distribution/package/plugin lane.

Implementation guarantees tested offline:

- exact manifest keys, environment names/required flags, versions, and five owned paths;
- only safe supported config defaults;
- exact profile payload copied into an isolated temporary Hermes home;
- blank-value `.env.EXAMPLE` generation without copying `.env`, auth, state, runtime, or user files;
- seven unified commands registered once under a fake plugin context;
- existing-profile collision without force;
- normal update preserves config and all user-owned state;
- force-config refreshes config while preserving user-owned state;
- force install refreshes owned files/config while preserving user-owned state;
- failed Hermes-version preflight leaves prior owned state byte-identical;
- authored and installed payload scans reject recognizable secret literals and private user paths.

## Verification

Verification is offline and uses temporary profile roots. Required final lanes:

```bash
python -m pytest -q tests/test_profile_distribution.py tests/test_unified_plugin.py tests/test_portable_package_integration.py
python -m pytest -q
python -m py_compile non_profit_hermes/*.py plugins/non-profit-hermes/*.py tests/test_profile_distribution.py
git diff --check
```

Results:

- focused distribution/package/plugin lane: `27 passed`;
- full repository lane: `335 passed, 69 subtests passed`;
- required `py_compile`: passed;
- YAML manifest/config and bundled skill validation: passed;
- package/plugin/distribution version parity: all exactly `1.0.0`;
- explicit ownership: exactly `distribution.yaml`, `SOUL.md`, `config.yaml`, `skills/non-profit-hermes`, and `plugins/non-profit-hermes`;
- authored distribution payload secret/raw-ID/private-path scan: passed;
- isolated installed-tree scan and install/update/force/collision/plugin-import tests: passed in the focused lane;
- protected Python package, plugin source, runtime shims, scripts, and generated public files: unchanged;
- `git diff --check`: passed.

One first-pass allowlist helper treated the untracked `skills/` directory as one entry and rejected it instead of enumerating its file. The corrected read-only check used `git status --untracked-files=all` and passed the exact ten-path task allowlist. No product or test code was changed to hide that diagnostic failure.

## Security and lifecycle

`env_requires` declares only variable names, descriptions, and required flags. It contains no secret, identifier, path, or provider-auth default. OpenAI Codex OAuth is configured after install with profile-scoped Hermes auth. Telegram and Google values belong in the installer's private environment.

Normal updates preserve local config and all user-owned data. `--force-config` deliberately replaces config while still preserving user-owned data. The installed Hermes implementation proves compatibility failures before copy leave prior owned files unchanged; it does not provide a general transactional rollback guarantee for arbitrary mid-copy failures. Exact rollback therefore uses a reviewed Git revision, separate Python-package reinstall, profile force-install, protected user-state backup, and operator verification.

No live profile was installed, updated, forced, inspected, or deleted. No plugin was enabled. No gateway was started. No Telegram or Google call was made. No Calendar event or public artifact was created or published.

## Limitations

- Runtime doctor is a downstream deliverable; installation acceptance remains a documented manual sequence until it exists and passes.
- Clean-machine and independent-checker acceptance are pending.
- The `v1.0.0` tag and release are not published by this task.
- The unified plugin is distribution-owned in source but is not thereby installed, enabled, migrated, or live-verified.
- The seven compatibility shims remain for one release and must never be enabled with the unified plugin.
- Current Hermes preserves user data across updates/force operations but exposes no general mid-copy transaction rollback API.
- Gateway activation, human Telegram canaries, Google identity/access, Calendar authorization, public-site parity, production migration, and physical-device acceptance remain untested here.
