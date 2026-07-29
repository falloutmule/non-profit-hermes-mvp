# NPH-V1 Documentation Reconciliation

**Task:** NPH-V1-010
**Captured:** 2026-07-21
**Production GitHub `main`:** `91143b3bacb46f799292027f1697376932b55403`
**Packaging evidence base:** `2276aa8f04b787e66d9eefd382fb32912660c7bb`

## Goal

Reconcile the canonical public documentation with the current inspected system while preserving older reports as dated historical evidence. This pass changes documentation only; it does not alter application code, plugins, profile/runtime state, generated public output, Google data, Calendar data, or gateway state.

## Evidence order

Conflicts were resolved using:

1. current direct runtime inspection;
2. current Git and GitHub state;
3. current passing tests;
4. `reports/NPH_V1_000_CURRENT_STATE.md` and JSON companion;
5. historical documentation;
6. inference.

## Files reconciled

- `README.md`
- `PROJECT_STATUS.md`
- `ARCHITECTURE.md`
- `OPERATIONS.md`
- `DEVELOPMENT.md`
- `SECURITY_AND_PRIVACY.md`
- `reports/README.md`
- `CLEANUP_MILESTONE_INDEX.md`
- `reports/NPH_V1_DOCUMENTATION_RECONCILIATION.md`

No prior report was modified.

## Current truth documented

- Production GitHub `main` remains `91143b3bacb46f799292027f1697376932b55403`; packaging commits are distinct and are not described as production.
- The read-only verified Telegram identity is `@HnonProfitBOT`.
- The authoritative runtime profile is `nonprofit` using `openai-codex/gpt-5.6-sol`.
- The separate nonprofit gateway is stopped.
- A separate Windows Scheduled Task launcher targets profile `nonprofit` and overrides the profile config port `8642` with intended port `8643`.
- Port `8643` was not listening; stale gateway metadata still claimed `running`; two additional generated service/startup paths reported by status were absent.
- The repository contains all seven canonical legacy plugin copies, manifest, installer, and read-only drift checker.
- The `nonprofit` profile-local plugin path is a Windows junction to the shared installed root.
- Seven legacy plugins are installed and enabled for `nonprofit`; all are disabled in `default`.
- Strict drift passed with only expected bytecode derivations and no missing/unexplained files.
- Telegram's registry contains `/daily`, `/need`, `/donation`, `/report`, `/task`, `/inventory`, and `/event`.
- Registry presence is not current dispatch proof while the gateway is stopped.
- `/daily` is locally verified as an approved-safe in-memory, no-generation, no-durable-refresh path.
- Current human-originated `/commands` and `/daily` canaries are untested.
- Historical user-supplied human-originated `/daily` evidence is dated 2026-07-12 and is labeled historical rather than current acceptance.
- Operational credential loaders use atomic candidate validation, lock, exact backup, atomic replacement, verification, cleanup, and rollback; `/daily` and sync dry-run intentionally refresh in memory only.
- Plugin installation is dry-run by default, requires explicit apply/target consent, creates timestamped directory backups, and restores on failed replacement.
- Current full-suite baseline is 235 passed plus 64 subtests.

## Stale claims corrected

- Removed the claim that canonical plugins exist only outside the repository.
- Removed current-status use of earlier suite sizes; those results remain valid only in their historical reports.
- Corrected CLEANUP-003 to complete; prior documents had treated it as unfinished.
- Corrected durable operational refresh from non-atomic to atomic/recoverable while preserving the intentional in-memory-only behavior of read-only paths.
- Replaced unqualified `live` command labels with registered/enabled/current-dispatch-untested classifications.
- Separated current stopped-runtime truth from historical live command evidence.
- Replaced historical event authorization language with the current per-event, non-reusable authorization boundary.
- Clarified that public generation, review, commit, push, and publication are separate gates.

## Supersession map

`reports/README.md` now maps old status, cleanup, command, Calendar, Google recovery, deployment, and test-count evidence to the current authority. Historical reports are preserved and linked; they are not deleted or silently rewritten.

## Privacy review

Canonical docs use placeholders for local roots and contain no token values, token fingerprints, bot numeric IDs, raw private chat/user IDs, OAuth payloads, private Google records, or credential contents. The documentation explains prohibited data categories without reproducing sensitive values.

## Implemented versus proposed

The docs distinguish the current script-based, seven-legacy-plugin system from later packaging targets. The importable `non_profit_hermes` package, unified plugin, installable profile distribution, runtime doctor, clean-install/update/rollback acceptance, production migration, and `v1.0.0` release are explicitly marked proposed or pending.

## Verification

Focused read-only test:

```text
python -m pytest -q tests/test_daily_read_only.py
5 passed in 0.17s
```

Full required lane:

```text
python -m pytest -q
235 passed, 64 subtests passed in 6.11s
```

Final stale-claim/identifier scan, internal-link validation, allowed-path check, public/generated-data non-mutation check, `git diff --check`, exact-parent check, commit, and clean-status verification are recorded in the task handoff because the report cannot self-reference its own final commit.

## Untested

- nonprofit gateway startup and effective `8643` bind;
- current human-originated `/profile`, `/model`, `/commands`, and `/daily` canaries;
- current live `/daily` Google reads and zero-write counters;
- public-site generation parity;
- physical-device acceptance;
- proposed package/distribution/unified-plugin/doctor and clean-install flows.

## Current limitation

This reconciliation makes repository documentation truthful at the inspected boundary. It does not make the stopped runtime live, make the legacy code portable, install a full profile, or complete the remaining packaging project.
