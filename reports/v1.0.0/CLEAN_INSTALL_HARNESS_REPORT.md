# NPH-V1-060A Clean-Install Harness Report

**Evidence date:** 2026-07-21
**Implementation parent:** `ec2d6961289087bf8216426ee578b774b8902649`
**Acceptance status in this report:** implementation verified; actual disposable run pending

## Deliverable

`scripts/clean_install_acceptance.py` is a fail-closed, restart-safe harness for the clean package/profile acceptance lane. Its supported invocation is:

```bash
python scripts/clean_install_acceptance.py \
  --source <exact-clean-repository-root> \
  --output-root <new-unique-child-of-hermes-cache> \
  --profile nonprofit-v1-test-<unique-suffix> \
  --json
```

The output root must not already exist. Evidence is preserved by default. The `--keep` option documents that safe behavior but does not weaken collision refusal.

## Admission controls

The harness performs no output write until it verifies:

- source is an existing Git top-level worktree;
- HEAD is an exact 40-character commit SHA;
- tracked and untracked source state is clean;
- source and output do not overlap;
- output is a new strict child of the active Hermes cache;
- isolated and active Hermes roots differ;
- the profile uses the `nonprofit-v1-test` disposable prefix;
- the profile is neither reserved nor already present;
- installed Hermes supports the current `profile install` command contract.

A collision, dirty source, unsafe archive member, unsupported runtime, or failed stage stops the workflow and records a stable secret-free failure code when an output run already exists.

## Disposable execution contract

After admission, the harness:

1. runs `git archive` for the admitted SHA;
2. safely extracts regular files/directories only and rejects traversal before extraction;
3. scans paths/content for excluded Git metadata, `.env`, auth/token/credential files, memories, sessions, databases, logs, caches, backups, private directories, token patterns, authorization values, and raw private IDs;
4. recreates a disposable Git index from the already-scanned archive for index-parity tests, without copying source `.git` metadata;
5. builds exactly one wheel and one sdist;
6. verifies version `1.0.0`, exact wheel members, exact console entry point, hashes, and package exclusions;
7. creates a fresh venv and performs a non-editable wheel installation with the test extra;
8. isolates `%LOCALAPPDATA%`, `HOME`, `USERPROFILE`, `HERMES_HOME`, and temporary directories under the run root while removing inherited profile and integration-secret selection;
9. runs the supported Hermes local-directory profile install into that isolated root;
10. proves no private state was installed and that unified-only model/plugin/version/ownership state is correct before synthetic staging;
11. creates only a synthetic `auth.json` mapping and an external synthetic credential placeholder—never `.env` or a real token-shaped value;
12. runs installed-wheel module and console offline strict JSON doctor commands from a cwd outside source;
13. requires equal healthy redacted reports and an unchanged profile snapshot;
14. loads the installed profile plugin in an isolated interpreter with sockets disabled and proves exactly seven commands and idempotent registration;
15. runs the full archive suite, compiles every package/script/test Python file, runs `git diff --check`, and verifies source-file hashes remain unchanged;
16. writes canonical secret-free `result.json` with `production_touched: false`.

## Unit verification

The initial 45-turn implementation run exhausted its budget. Independent checking found 29 focused tests passed and one RED: the CLI defined `main()` but lacked its executable module guard, so `--help` returned no text. One bounded 30-turn continuation added the guard. Both workers exhausted their declared budgets; no third worker ran.

After independent hardening for archive-index parity and source-safe runtime scanner sentinels, local verification passed:

```text
Focused clean-install/doctor/distribution/package lane after the bounded archive-scan repair: 34 passed
Full repository suite after the bounded archive-scan repair: 363 passed, 69 subtests passed
Harness/test py_compile: passed
CLI --help contract: passed
git diff --check: passed
Protected package/profile/plugin/generated-public parity: passed
```

Unit tests fake all subprocess and integration boundaries. They do not perform an actual profile install, wheel install, network call, gateway action, Google/Calendar action, public generation, or publication.

The first orchestrator execution at committed harness `f4b1a43c6f9914592f1bfe71fd0adcd2d7762469` stopped fail-closed at `archive_privacy`. Its secret-free evidence reported only synthetic redaction fixtures under `tests/` plus a false positive on Python keyword arguments named `client_secret`; no credential value was reported or copied. The bounded repair keeps private-path scanning active in tests, scopes literal credential scanning to distributable/runtime material, and requires a quoted mapping-style client-secret value instead of treating ordinary Python identifiers as credentials. The failed run remains preserved as evidence and is not called a clean-install PASS.

## Evidence schema

The actual run writes `result.json` containing only:

- schema/status/source SHA;
- normalized argv with `<SOURCE>`, `<EXTRACTED>`, `<OUTPUT>`, and `<WHEEL>` placeholders;
- passed/failed stages and stable failure code;
- wheel/sdist hashes, versions, and member counts;
- doctor mode/version/exit/summary;
- profile-contract booleans;
- exact seven command names;
- test summary;
- limitations and `production_touched: false`.

It does not store command stdout/stderr, environment values, credential payloads, profile private data, synthetic values, raw IDs, or token fingerprints.

## Remaining gate

This report does **not** claim clean-install PASS. The orchestrator must commit the harness, run that exact clean commit once in a unique cache-root directory, inspect `result.json`, independently verify source/live-profile isolation and evidence secrecy, and then commit the final NPH-V1-060 acceptance reports. Update, failed-update rollback, removal, legacy migration, and compatibility rollback remain bounded follow-on acceptance work.
