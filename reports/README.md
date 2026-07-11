# Reports Index — Non-Profit Hermes MVP

**Last updated:** 2026-07-11 (CLEANUP-001)

Reports in this repository document the building, wiring, and verification of each system component. Some reports are current verification evidence; others are historical snapshots of superseded runtime states.

**Historical reports may describe states, commits, or configurations that no longer reflect the current system.** Always cross-reference with [PROJECT_STATUS.md](../PROJECT_STATUS.md) for the current state.

---

## Current verification

These reports contain live-verified evidence that remains accurate:

| Report | Subject |
|--------|---------|
| [LIVE_EVENT_COMMAND_REPORT.md](../LIVE_EVENT_COMMAND_REPORT.md) | EVENT-003 draft-first `/event` live verification |
| [EVENT_CALENDAR_PRIVACY_REPORT.md](../EVENT_CALENDAR_PRIVACY_REPORT.md) | EVENT-001 calendar publication privacy gate |
| [EVENT_DRAFT_BACKEND_REPORT.md](../EVENT_DRAFT_BACKEND_REPORT.md) | EVENT-002 durable event-draft backend (amended with final commit) |

---

## Historical — Telegram command wiring

These reports document the initial wiring of each Telegram command. They were written during implementation and may contain stale "pending activation" or "awaits gateway session" wording. The commands are now all live and verified.

| Report | Command | Note |
|--------|---------|------|
| [LIVE_DAILY_LINKS_AND_DEDUP_REPORT.md](../LIVE_DAILY_LINKS_AND_DEDUP_REPORT.md) | `/daily` v002 | Superseded by v003 |
| [LIVE_DAILY_SUMMARY_TRIM_REPORT.md](../LIVE_DAILY_SUMMARY_TRIM_REPORT.md) | `/daily` v003 | Historical; commit now recorded |
| [LIVE_NEED_COMMAND_REPORT.md](../LIVE_NEED_COMMAND_REPORT.md) | `/need` | Historical |
| [LIVE_NEED_SLOPPY_INTAKE_FIX_REPORT.md](../LIVE_NEED_SLOPPY_INTAKE_FIX_REPORT.md) | `/need` | Historical |
| [LIVE_DONATION_COMMAND_REPORT.md](../LIVE_DONATION_COMMAND_REPORT.md) | `/donation` | Historical; live verified |
| [LIVE_DONATION_PLUGIN_REGISTRATION_REPORT.md](../LIVE_DONATION_PLUGIN_REGISTRATION_REPORT.md) | `/donation` | Historical; plugin registered |
| [LIVE_REPORT_COMMAND_REPORT.md](../LIVE_REPORT_COMMAND_REPORT.md) | `/report` | Historical; live verified |
| [LIVE_TASK_COMMAND_REPORT.md](../LIVE_TASK_COMMAND_REPORT.md) | `/task` | Historical; live verified |
| [LIVE_INVENTORY_COMMAND_REPORT.md](../LIVE_INVENTORY_COMMAND_REPORT.md) | `/inventory` | Historical; live verified |

---

## Historical — Deployment proofs

These reports document deployment verification at various points in the project. The deployment process and Pages source have since been clarified. Current Pages source is `main /docs`.

| Report | Subject |
|--------|---------|
| [BROWSER_VISIBLE_DEPLOYMENT_PROOF_REPORT.md](../BROWSER_VISIBLE_DEPLOYMENT_PROOF_REPORT.md) | Browser screenshot proof (historical) |
| [PAGES_WIRING_REPORT.md](../PAGES_WIRING_REPORT.md) | Pages wiring pattern |
| [LIVE_PUBLIC_FETCH_PROOF_REPORT.md](../LIVE_PUBLIC_FETCH_PROOF_REPORT.md) | Live fetch proof (historical) |
| [LIVE_SITE_SYNC_MISMATCH_REPORT.md](../LIVE_SITE_SYNC_MISMATCH_REPORT.md) | Site sync mismatch diagnosis (historical) |
| [CACHEBUST_PUBLIC_FETCH_REPORT.md](../CACHEBUST_PUBLIC_FETCH_REPORT.md) | Cache-bust fetch proof (historical) |
| [CANONICAL_LIVE_DEPLOYMENT_PROOF_REPORT.md](../CANONICAL_LIVE_DEPLOYMENT_PROOF_REPORT.md) | Canonical deployment proof (historical) |
| [DEPLOYMENT_SOURCE_DIAGNOSIS_REPORT.md](../DEPLOYMENT_SOURCE_DIAGNOSIS_REPORT.md) | Deployment source diagnosis (historical) |
| [VISIBLE_SYNC_RENDERING_REPORT.md](../VISIBLE_SYNC_RENDERING_REPORT.md) | Sync rendering proof (historical) |
| [docs/DOCS_SYNC_UPDATE_REPORT.md](../docs/DOCS_SYNC_UPDATE_REPORT.md) | Docs sync update (historical) |

---

## Historical — Privacy/security fixes

| Report | Subject |
|--------|---------|
| [REPORT_EXPORT_PRIVACY_FIX_REPORT.md](../REPORT_EXPORT_PRIVACY_FIX_REPORT.md) | Report export privacy fix |
| [REPORT_ACTIVE_FOLLOWUP_FIX_REPORT.md](../REPORT_ACTIVE_FOLLOWUP_FIX_REPORT.md) | Active follow-up fix |
| [REPORT_LIVE_ACTIVE_FOLLOWUP_DIAGNOSIS.md](../REPORT_LIVE_ACTIVE_FOLLOWUP_DIAGNOSIS.md) | Follow-up diagnosis |

---

## Historical — Google asset wiring

| Report | Subject |
|--------|---------|
| [GOOGLE_WRITE_CAPABILITY_REPORT.md](../GOOGLE_WRITE_CAPABILITY_REPORT.md) | Initial write capability proof. **Historical:** describes pre-EVENT-001 calendar export policy. |
| [GOOGLE_ASSETS_WIRING_REPORT.md](../GOOGLE_ASSETS_WIRING_REPORT.md) | Google Sheets/Calendar/Drive wiring |
| [APPROVED_SAFE_SYNC_REPORT.md](../APPROVED_SAFE_SYNC_REPORT.md) | Approved-safe sync initial proof |

---

## Diagnostics

| Report | Subject |
|--------|---------|
| [TELEGRAM_INTAKE_ROUTER_REPORT.md](../TELEGRAM_INTAKE_ROUTER_REPORT.md) | Router design and implementation |

---

## Archive candidates

The following root-level proof artifacts are historical and do not represent the current deployment. They are candidates for archival (CLEANUP-006):

```
LIVE_CHECK_001.html
proof-8194ce0.html
proof-live-fetch/
proof-live-fetch-cachebust/
proof-canonical-live-fetch-2/
proof-browser-source/
proof-browser-screenshots/
proof-external-mismatch-diagnosis/
```

The active deployment proof is `docs/deployment-proof.html`.
