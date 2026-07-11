# Operations — Non-Profit Hermes MVP

**Last updated:** 2026-07-11 (CLEANUP-001)

## Daily operations

### `/daily` — daily brief

The `/daily` command produces a read-only summary for the operations team. It includes:

1. Calendar events for today
2. Open urgent requests
3. Donation pickups/drop-offs
4. Volunteer gaps
5. Inventory shortages
6. Website links
7. Follow-ups due
8. Sensitive items needing human review
9. Completed items since last brief (count summaries)

**Version:** `website-links-dedup-003`

Calendar entries are deduplicated by title for display only. Source Sheet rows are never deleted.

### `/daily` versus website publication

**Important:** Currently `/daily` calls `run_sync()` which writes `docs/` files. This means a normal `/daily` call can dirty the Git working tree. It does **not** commit or push those files.

The Telegram sync marker can be newer than the public website because of this.

**Target design (planned cleanup):**

| Action | Behavior |
|--------|----------|
| `/daily` | Read-only summary only; no filesystem mutation |
| `python scripts/sync_approved_safe_data.py` | Explicit local generation |
| `/publish` | Future: approval-gated, auditable publication |

Until the design split is implemented, be aware that `/daily` modifies `docs/`. Do not assume the public site is current just because `/daily` ran.

## Intake commands

All write commands use draft-first intake:

| Command | Creates | Default status | Default privacy |
|---------|---------|----------------|-----------------|
| `/need <text>` | Requests row | needs-info | private-review |
| `/donation <text>` | Donations row | needs-info | private-review |
| `/report <text>` | Reports row | needs-info | private-review |
| `/task <text>` | Tasks row | needs-info | internal |
| `/inventory <text>` | Inventory row (upsert) | needs-info | internal |
| `/event <text>` | CalendarLog draft | needs-info | private-review |

After creating a draft, the router lists missing fields. Send plain text follow-up with `field=value` pairs to complete the record. No need to retype the ID — the active draft pointer tracks it.

When status reaches `ready`, the active pointer clears automatically for most draft types. **Exception:** event drafts remain active at `ready` while `CalendarEventID` is blank (awaiting promotion). Event pointers clear after confirmed promotion, cancellation, or rejection.

### Follow-up behavior

- Plain follow-up text attaches to the active draft in the same chat.
- Explicitly naming an ID (e.g., `DON-47D11AAA`) overrides the active pointer.
- Multiple open drafts in the same chat produce an ambiguity response.
- The follow-up chain tries: event → report → task → inventory → donation → need.

## Publication workflow

### Current (manual)

1. Run `python scripts/sync_approved_safe_data.py`
2. Review `git diff` in `docs/`
3. Check for privacy sentinels
4. Commit generated output
5. Push to `main`
6. GitHub Pages auto-builds from `main /docs`

### Privacy checklist before publishing

Before committing a new snapshot:

- [ ] No private-review or private-hold records in approved JSON
- [ ] No draft or needs-info status records exported
- [ ] No donor contact information exported
- [ ] No internal Task/Inventory IDs in board log (P0 gap)
- [ ] No raw Calendar event details (only CalendarLog public fields)
- [ ] Deployment marker present on all pages
- [ ] Record counts match expected values

## Google Sheets maintenance

### AuditLog growth

The AuditLog is append-only and grows with every operation. The generic Sheet reader currently stops at row 100, which means newer audit entries may not be read by `/daily` or the sync script. This is a known P0 issue (CLEANUP-002).

### Test records

The Sheet contains historical test records (e.g., `REQ-WRITE-TEST-001`, `DON-WRITE-TEST-001`, `EVT-1718BB9F`). These are clearly marked as test/fake records. Do not delete them during cleanup without explicit authorization.

### Data hygiene

A read-only audit script is planned (CLEANUP-007) to report:
- duplicate primary IDs
- rows marked TEST/fake/simulated
- stale drafts
- orphaned active pointers
- public rows missing explicit approval

Any live Sheet deletion or backfill must be a separate user-authorized task.

## Event operations

### Current state

- `/event` creates CalendarLog drafts only (EVT-XXXXXXXX).
- Calendar creation is **disabled** in the live plugin.
- No live Google Calendar event has been created by the draft-first `/event` flow or EVENT-004 promotion path. Historical safe fake direct backend test events exist.

### EVENT-003 verified flow

1. `/event <text>` creates a draft with `CalendarEventID` blank.
2. Follow-up text updates the draft fields.
3. Draft can be cancelled/rejected without any Calendar effect.
4. The required read-only Calendar search returns 0 matches (no event created).

### EVENT-004 (unstarted)

EVENT-004 will authorize the first live Calendar promotion:
1. Authorize one safe fake Calendar event.
2. Perform controlled router promotion.
3. Verify same-row `CalendarEventID` update.
4. Verify idempotent retry (no duplicate event).
5. Verify private event exclusion from public docs.
6. Decide final confirmation/plugin gate policy.

EVENT-004 is blocked until P0 cleanup items are resolved.
