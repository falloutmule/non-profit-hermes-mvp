# Cleanup Milestone Index

**Canonical status:** Google recovery and CLEANUP-007 documentation closeout. This index is the canonical status entry point for the records named below. It does not grant an operational authorization.

## Current canonical truth

- The recovery repairs are integrated at `dc2ef634c4af117ebfc1c024c9608a257318384d`: port-0 loopback redirect contract, callback/state/scope guards, real Flow redirect binding, guarded candidate validation, and explicit live arming.
- The integrated documentation base is `af2149648b78ae2b05004b632c5b399c4b35d9d9`: `975fde6` integrated CLEANUP-006C and `af21496` integrated CLEANUP-007C. Their source checker records are `t_cdd46aea` and `t_5f852df8`, both completed PASS.
- GR-CHECK-001 (`t_ed2752a1`) completed PASS against `dc2ef634`: its redacted evidence chain supports one successful callback/exchange, an ACCEPTED candidate with the exact eight-scope contract, restricted atomic promotion with rollback-only backup, and post-promotion bounded reads.
- CLEANUP-007B-R2 (`t_51a5542e`) completed PASS: 182 governed records, one `ABANDONED_DRAFT_REVIEW`, one `EVIDENCE_RETAIN`, 180 `UNKNOWN_MANUAL_REVIEW`, five confirmed exact Calendar IDs per pass, and zero mutation calls.
- CLEANUP-006C and CLEANUP-007C are integrated and independently checked. The retention policy authorizes zero current changes: no archive, delete, edit, publication, or automatic action.

## Canonical decisions and limitations

- Candidate acceptance is not a reusable authorization. The documented recovery flow requires validation before promotion and preserves the operational credential on a failed candidate path.
- The current application loaders remain non-atomic for durable refresh. The recovery-only `atomic_promote` helper is not a description of those loaders.
- R2 performed only in-memory refresh for its bounded read-only inventory; the operational token file was unchanged in that run.
- A Calendar delete may retain a cancelled tombstone. The verified condition is one cancelled tombstone and zero active exact-ID matches; no recreation is authorized.
- Gateway restart and independent deployed-runtime validation were not performed. No plugin deployment, publication, push, merge, archive, or delete is authorized by this index.
- Direct installer dry-run has a known Windows CRLF checkout/manifest exit-2 limitation. Tracked Git blobs, focused tests, strict runtime drift, and full-suite evidence remain separately recorded; the limitation is not repaired by documentation.

## Historical records and stale-claim handling

The following remain retained evidence or historical context and must not be read as current authorization or current runtime proof:

- `EVENT_004_LIVE_CALENDAR_PROMOTION_REPORT.md` and the EVENT-003/EVENT-004 passages in older status/operations/security documents are historical controlled-event evidence.
- `CLEANUP_006B_*` decision and forensic packets preserve the earlier redirect/recovery analysis. They are historical evidence, not a current permission to re-run an OAuth flow.
- Earlier statements that a documentation closeout was pending, that an old offline test count was the latest suite result, or that a remote branch matched at a past instant are historical observations only. Current repository state must be queried with Git.
- Legacy insecure URL-evidence artifacts are quarantined/non-authoritative and are not named as a source of current approval.

## Next-wave proposal — no authorization granted

A later wave may consider only after a new human decision:

1. a new read-only, fresh inventory and exact-ID reconciliation for the 180 manual-review records;
2. separate review of the single abandoned draft and the retained evidence record, with no automatic classification override;
3. a separately scoped durable-refresh/promotion hardening proposal for the current non-atomic loaders; and
4. an installer CRLF/manifest remediation proposal confined to the installer/runtime-plugin boundary.

Any archive or delete would require the exact targets, a fresh counts-only recheck, reversible archive and restore evidence, an independent checker, and explicit data-owner/operations, privacy, and system-owner authorization. Any gateway/plugin/publication action would require its own human-approved scope and deployment verification. This index grants none of those authorizations.
