# NPH-V1-050 Runtime Doctor Report

**Evidence date:** 2026-07-21
**Package version:** `1.0.0`
**Offline-doctor commit:** `60c7b98b4c489800bd798ffe0735292858879ce1`
**Live-readonly parent:** `60c7b98b4c489800bd798ffe0735292858879ce1`

## Scope delivered

The package provides equivalent entry points:

```bash
python -m non_profit_hermes.doctor
nonprofit-hermes doctor
```

Supported modes and options are:

```text
--offline
--live-readonly
--profile <name>
--json
--strict
```

The result contract is deterministic and redacted. Exit codes are:

```text
0 = healthy
1 = warning or partial
2 = blocking configuration failure
3 = runtime failure
4 = privacy or integrity failure
```

Strict mode promotes a warning to exit `2`; it does not hide or relabel the originating check.

## Offline checks

Offline mode verifies package import/version/path, expected package resources, source-path safety, source commit when available, profile existence and configuration, model/provider metadata, auth metadata presence, credential-file readability, required environment names, unified plugin discovery and enablement, legacy-plugin exclusion, profile-distribution files/manifest/version alignment, and private-file/literal exclusions. Gateway, Telegram, Google, and public-site probes are explicit neutral skips in offline mode.

## Live-readonly checks

Live-readonly mode adds granular secret-free checks for:

- one profile gateway process and matching PID/runtime profile;
- one matching Windows Scheduled Task with no credential literal;
- configured, unique API listener owned by the gateway;
- no restart/error retry loop or duplicate poller candidate;
- Telegram adapter loaded and healthy;
- exactly the seven expected unified commands with no legacy overlap;
- Telegram HTTPS `getMe` identity matched to the separately configured public username;
- valid, unexpired Google credentials with required read scopes;
- one minimal Sheets `values.get` and one Calendar `calendarList.get`;
- approved-safe local files, marker, and privacy scan;
- optional HTTPS published-site marker.

Default probes are bounded and read-only. They do not start, stop, restart, install, or uninstall a gateway or Scheduled Task; send messages or alter Telegram polling/commands; refresh or persist credentials; append/update/clear Sheets; insert/update/delete Calendar events; regenerate public files; invoke Git; or publish.

## RED to GREEN evidence

### NPH-V1-050A

The first implementation run exhausted its 45-turn budget after reaching focused GREEN. The independent full suite exposed one stale wheel-metadata allowlist: the supported console entry point correctly added `entry_points.txt`, but the existing archive test rejected it. One bounded continuation added an exact entry-point assertion. Both workers exhausted their declared budgets; no third worker ran. The orchestrator independently verified and committed the exact six-file candidate.

Verified after reconciliation:

```text
Focused doctor/package/distribution lane: 31 passed
Full repository lane: 341 passed, 69 subtests passed
py_compile: passed
wheel entry_points.txt exact value: passed
external wheel missing-profile safe failure/redaction: passed
```

An attempted external-wheel complete-fake-profile strict rerun was blocked by command-approval timeout. It was not retried, and this report does not claim it passed. Source CLI fake-profile behavior remains covered by the offline test suite.

### NPH-V1-050B

The first live-readonly run exhausted its 45-turn budget with one deliberate RED: 26 tests passed and the default public-site probe remained a fail-closed stub. One bounded continuation implemented the local allowlisted scan and HTTPS GET marker check. It also exhausted its declared budget; no third worker ran. Independent verification produced:

```text
Focused live/offline/distribution lane: 27 passed
Full repository lane: 350 passed, 69 subtests passed
py_compile: passed
protected distribution/plugin/generated-public source parity: passed
```

The focused tests inject adapters and monkeypatch only process, Scheduled Task, URL, Google, and filesystem boundaries. They prove healthy strict exit `0`, configuration/runtime/integrity exits `2`/`3`/`4`, strict warning promotion, exception-detail redaction, offline zero live calls, exact read-only Google/Telegram/public call shapes, discarded numeric identity/private response data, and unchanged credential/profile/public bytes and modification times.

Independent runtime-shape review then found that current Hermes writes Telegram status under `gateway_state.json` → `platforms.telegram`, keeps repeated-start evidence in `gateway-starts.log`, and identifies the Scheduled Task through its profile-specific task/launcher name rather than a literal `--profile` flag in the task action. The adapter and fake were corrected to accept that current read-only schema, count only ledger timestamps from the last 120 seconds, and retain fail-closed behavior for invalid state. Focused and full lanes were rerun after this correction.

## Privacy and redaction

Check messages and metadata redact token-, secret-, password-, authorization-, cookie-, API-key-, bearer-, OAuth-token-, raw-chat-ID-, and user-home-path patterns. Live adapter exceptions expose only a stable error class and severity. The doctor does not serialize command lines, Scheduled Task definitions, environment values, credential payloads, numeric bot identity, private Sheet values, Calendar event bodies, or live HTTP response bodies.

## Limitations and untested state

- No production `--live-readonly` invocation was performed in NPH-V1-050.
- No production gateway, Scheduled Task, profile, plugin, Telegram, Google, Calendar, or public site was modified.
- No human-originated Telegram canary was performed.
- Source and fake-backed verification is not clean-install acceptance.
- The gateway was last inventoried as stopped, with stale runtime metadata and a config/launcher port disagreement; this work does not resolve that operational state.
- A missing live publication URL is a warning and therefore blocks strict mode; it is not reported as a publication PASS.
- The complete external-wheel fake-profile strict scenario remains for NPH-V1-060 because the NPH-V1-050A attempt was approval-blocked.

## Acceptance boundary

NPH-V1-050 establishes the doctor implementation and local evidence needed by clean-install acceptance. NPH-V1-060 must install from a clean checkout/archive into disposable roots, run the wheel console/module commands outside the source tree, prove update/remove/failed-update rollback, and rerun offline strict with fake integrations before any production migration.
