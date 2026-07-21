# Cleanup Milestone Index

**Current index captured:** 2026-07-21

This file preserves cleanup history. It is no longer the primary current-system status page. Use [PROJECT_STATUS.md](PROJECT_STATUS.md) and [reports/NPH_V1_000_CURRENT_STATE.md](reports/NPH_V1_000_CURRENT_STATE.md) for current Git/runtime truth, and [reports/README.md](reports/README.md) for supersession.

## Current repository and runtime boundary

- Production GitHub `main`: `91143b3bacb46f799292027f1697376932b55403`
- Packaging current-state evidence commit: `2276aa8f04b787e66d9eefd382fb32912660c7bb`
- Runtime profile/model: `nonprofit`, `openai-codex/gpt-5.6-sol`
- Bot identity: `@HnonProfitBOT`, verified read-only
- Gateway: stopped; current live dispatch and human canaries untested
- Plugins: seven canonical legacy copies tracked, seven installed/enabled for `nonprofit`, strict drift clean except expected bytecode derivations
- Tests: 235 passed, 64 subtests passed

Packaging work is in progress. No unified plugin, installable profile distribution, importable package, runtime doctor, clean-install acceptance, production migration, or `v1.0.0` release exists yet.

## Milestone state

| Milestone | Current interpretation |
|---|---|
| CLEANUP-002 — export safety | Complete; deny-by-default consent/status/privacy gates, deduplication, escaping, and aggregate board log implemented |
| CLEANUP-003 — `/daily` read-only separation | Complete; `/daily` uses an in-memory approved-safe snapshot and does not generate public files or persist refresh |
| CLEANUP-004 — runtime plugin reproducibility | Complete for seven legacy plugins; canonical sources, manifest, installer, backups, rollback, and drift checker exist |
| Atomic OAuth refresh closeout | Complete in source and synthetic tests; operational loaders use candidate validation, lock, exact backup, atomic replace, verification, and rollback |
| EVENT-004 — controlled Calendar promotion | Historical bounded acceptance only; no standing authority for another event |
| Google recovery/retention work through CLEANUP-007 | Historical accepted evidence and zero-change/manual-review decisions; not a current runtime-health claim |
| NPH-V1 packaging/reconciliation | In progress on `packaging/non-profit-hermes-v1`; proposed package/distribution/unified-plugin/doctor artifacts remain unimplemented |

## Corrected stale boundaries

The following older statements are superseded:

- The repository **does** contain canonical copies of all seven legacy runtime plugins.
- CLEANUP-003 is complete; `/daily` no longer generates `docs/`.
- Operational durable refresh is atomic/recoverable; `/daily` and dry-run intentionally refresh in memory only.
- The current test baseline is 235 passed plus 64 subtests, not earlier cleanup/event counts.
- Historical command and event acceptance does not prove present live dispatch.
- The stopped gateway, port mismatch, stale metadata, and pending human canaries remain current limitations.

## Historical recovery and retention evidence

Recovery repairs and the CLEANUP-006/CLEANUP-007 records remain retained evidence for their exact dates and commits. Their bounded candidate acceptance, promotion, counts-only inventory, manual-review classifications, and zero-change retention decision are not reusable authorization.

A cancelled Calendar tombstone with zero active exact-ID matches remains a lifecycle result, not an instruction to recreate an event. Historical per-event promotion authority was consumed and does not authorize another Calendar mutation.

## Authorization boundary

This index authorizes no gateway lifecycle action, plugin deployment, Google mutation, Calendar event, public generation/publication, Git push/merge/tag, archive, deletion, or cleanup. Those actions require their own exact scope, backups, verification, and approval.

Old worktrees and branches remain until containment and later cleanup gates authorize removal. Public-generation parity remains untested in the 2026-07-21 inventory. Historical evidence must be preserved and labeled rather than deleted to make the repository appear current.
