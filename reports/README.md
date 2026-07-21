# Reports Index — Non-Profit Hermes MVP

**Current index captured:** 2026-07-21

Reports are immutable point-in-time evidence unless a report explicitly says otherwise. A passing historical report does not prove present runtime state, grant a standing authorization, or override current Git/runtime inspection.

## Current authority

Use these sources in order:

1. current direct runtime inspection;
2. current Git and GitHub state;
3. current passing tests;
4. [NPH-V1-000 current-state report](NPH_V1_000_CURRENT_STATE.md) and its [machine-readable companion](NPH_V1_000_CURRENT_STATE.json);
5. [PROJECT_STATUS.md](../PROJECT_STATUS.md);
6. historical reports;
7. inference.

The current-state report was captured on 2026-07-21 and committed on the packaging branch at `2276aa8f04b787e66d9eefd382fb32912660c7bb`. Production GitHub `main` remains `91143b3bacb46f799292027f1697376932b55403`. The documentation reconciliation report is [NPH_V1_DOCUMENTATION_RECONCILIATION.md](NPH_V1_DOCUMENTATION_RECONCILIATION.md).

## Supersession map

| Older document or report family | What remains valid | Current authority / correction |
|---|---|---|
| Pre-2026-07-21 `PROJECT_STATUS.md` content | Dated cleanup and event evidence | [PROJECT_STATUS.md](../PROJECT_STATUS.md) now states current Git/runtime truth and the 235 + 64-subtest baseline |
| [CLEANUP_MILESTONE_INDEX.md](../CLEANUP_MILESTONE_INDEX.md) through 2026-07-15 | Recovery, retention, and cleanup decisions at those dates | Current system/runtime status comes from NPH-V1-000 and rewritten canonical docs; old no-action language is not a claim that atomic refresh or plugin copies are absent |
| [CLEANUP_003_DAILY_READ_ONLY_REPORT.md](../CLEANUP_003_DAILY_READ_ONLY_REPORT.md) | `/daily` implementation evidence and historical human-originated response dated 2026-07-12 | `/daily` remains read-only locally; current live dispatch/zero-write canary is untested while gateway is stopped |
| [CLEANUP_004_RUNTIME_PLUGIN_REPRODUCIBILITY_REPORT.md](../CLEANUP_004_RUNTIME_PLUGIN_REPRODUCIBILITY_REPORT.md) | Canonical plugin/installer design and disposable proof | Repository now contains seven canonical plugin copies; 2026-07-21 strict installed drift passed |
| `LIVE_*_COMMAND_REPORT.md` files | Historical implementation and command-specific acceptance | Commands are registered and plugins enabled; current dispatch is not proven with the stopped gateway |
| [EVENT_004_LIVE_CALENDAR_PROMOTION_REPORT.md](../EVENT_004_LIVE_CALENDAR_PROMOTION_REPORT.md) and earlier EVENT reports | One bounded historical promotion/draft proof | No reusable Calendar authority; every future promotion needs fresh per-event authorization |
| Deployment proof and Pages reports | Dated canonical/browser evidence | Pages source is `main /docs`; no new generation/publication or parity check occurred in the 2026-07-21 inventory |
| [GOOGLE_RECONNECT_REPORT.md](../GOOGLE_RECONNECT_REPORT.md) and recovery packets | Bounded recovery evidence | Operational loaders now use atomic refresh persistence; `/daily` and dry-run intentionally remain in-memory only |
| Historical test counts | Results for those exact commits | Current required full-suite result is 235 passed, 64 subtests passed |

## Current verification evidence

- [NPH_V1_000_CURRENT_STATE.md](NPH_V1_000_CURRENT_STATE.md) — current Git/GitHub, repository, profile, plugin, command registry, launcher/port, and test inventory
- [NPH_V1_000_CURRENT_STATE.json](NPH_V1_000_CURRENT_STATE.json) — machine-readable companion; restricted evidence may contain additional safe-for-internal-inventory metadata and is not a public status summary
- [NPH_V1_DOCUMENTATION_RECONCILIATION.md](NPH_V1_DOCUMENTATION_RECONCILIATION.md) — canonical documentation changes and validation
- [COMPLETION_REFRESH_001_HANDOFF.md](COMPLETION_REFRESH_001_HANDOFF.md) — atomic refresh closeout using synthetic files
- [COMPLETION_INSTALLER_001_HANDOFF.md](COMPLETION_INSTALLER_001_HANDOFF.md) — disposable plugin install, backup, rollback, and strict drift closeout

## Historical command evidence

These reports document command implementation/wiring. Treat every live claim as dated historical evidence, not current runtime proof:

- [LIVE_DAILY_LINKS_AND_DEDUP_REPORT.md](../LIVE_DAILY_LINKS_AND_DEDUP_REPORT.md)
- [LIVE_DAILY_SUMMARY_TRIM_REPORT.md](../LIVE_DAILY_SUMMARY_TRIM_REPORT.md)
- [LIVE_NEED_COMMAND_REPORT.md](../LIVE_NEED_COMMAND_REPORT.md)
- [LIVE_NEED_SLOPPY_INTAKE_FIX_REPORT.md](../LIVE_NEED_SLOPPY_INTAKE_FIX_REPORT.md)
- [LIVE_DONATION_COMMAND_REPORT.md](../LIVE_DONATION_COMMAND_REPORT.md)
- [LIVE_DONATION_PLUGIN_REGISTRATION_REPORT.md](../LIVE_DONATION_PLUGIN_REGISTRATION_REPORT.md)
- [LIVE_REPORT_COMMAND_REPORT.md](../LIVE_REPORT_COMMAND_REPORT.md)
- [LIVE_TASK_COMMAND_REPORT.md](../LIVE_TASK_COMMAND_REPORT.md)
- [LIVE_INVENTORY_COMMAND_REPORT.md](../LIVE_INVENTORY_COMMAND_REPORT.md)
- [LIVE_EVENT_COMMAND_REPORT.md](../LIVE_EVENT_COMMAND_REPORT.md)

## Historical privacy, Calendar, and publication evidence

- [CLEANUP_002_EXPORT_SAFETY_REPORT.md](../CLEANUP_002_EXPORT_SAFETY_REPORT.md)
- [EVENT_CALENDAR_PRIVACY_REPORT.md](../EVENT_CALENDAR_PRIVACY_REPORT.md)
- [EVENT_DRAFT_BACKEND_REPORT.md](../EVENT_DRAFT_BACKEND_REPORT.md)
- [EVENT_004_LIVE_CALENDAR_PROMOTION_REPORT.md](../EVENT_004_LIVE_CALENDAR_PROMOTION_REPORT.md)
- [REPORT_EXPORT_PRIVACY_FIX_REPORT.md](../REPORT_EXPORT_PRIVACY_FIX_REPORT.md)
- [APPROVED_SAFE_SYNC_REPORT.md](../APPROVED_SAFE_SYNC_REPORT.md)
- [PAGES_WIRING_REPORT.md](../PAGES_WIRING_REPORT.md)
- [CANONICAL_LIVE_DEPLOYMENT_PROOF_REPORT.md](../CANONICAL_LIVE_DEPLOYMENT_PROOF_REPORT.md)

## Historical proof artifacts

Root proof HTML, saved fetches, screenshots, and legacy Jekyll files are retained historical evidence. They do not establish current deployment parity. The active generated site remains under `docs/`; do not delete evidence or regenerate public data without separate authorization.
