# CLEANUP-007C Record Retention and Dry-Run Policy

**Status:** Policy and dry-run specification only; no authorization to mutate records
**Scope:** Governed Google Sheets records and their paired CalendarLog records
**Evidence basis:** Counts-only summary `CLEANUP_007B_LIVE_INVENTORY_SUMMARY_R2.json`
**Independent verification:** CLEANUP-007B checker task `t_51a5542e`

## 1. Purpose and boundary

This document defines a deny-by-default policy for classifying records as `retain`, `archive-candidate`, `delete-candidate`, or `manual-review`, and defines a read-only dry-run that may propose those states. It is not an authorization to archive, delete, edit, backfill, publish, or otherwise mutate any Google Sheet, Calendar event, local evidence file, token, gateway, plugin, or public surface.

Policy classification and authorization are separate:

- A policy state describes what a later, separately authorized operation might consider.
- An authorization names the exact scope, actor, operation, evidence, and time window for that operation.
- A dry-run never supplies authorization. A `delete-candidate` result is only a proposal and must not be executed automatically.
- Missing, malformed, stale, partial, private, or contradictory evidence fails closed to `manual-review` or `retain` as required by the precedence rules below.

The current recommendation is **zero changes and zero automatic delete candidates**. No current record is approved for automatic archive or delete.

## 2. Privacy and operational safety

### 2.1 Data minimization

The dry-run may consume only a counts-only authoritative inventory summary plus safe references and cryptographic hashes. It must not read, print, copy, persist, or transmit private record contents. In particular, do not include names, contact details, addresses, descriptions, notes, medical or crisis details, raw row values, full event payloads, access tokens, refresh tokens, credential paths, or private evidence contents in a report, log, test output, commit, or public surface.

Safe dry-run evidence is limited to:

- source and tab names;
- opaque, non-content `safe_ref` values;
- row ordinals only when needed for reconciliation;
- SHA-256 hashes of approved canonicalized inputs or outputs;
- counts, timestamps, policy version, decision codes, and status values;
- authorization and audit references that do not contain personal data or secrets.

A hash is a reference and integrity check, not permission to expose the underlying value. Do not infer or disclose a raw identifier from a hash.

### 2.2 Always-retain boundary

Personal data and real operational data are always `retain` / `do-not-touch` unless a separate, explicit, approved policy specifically covers the data and operation. This includes data about real people, real donors, requests, inventory, tasks, reports, commitments, or live operations, even where a row appears old, duplicated, incomplete, or abandoned.

Evidence needed to establish accountability, privacy decisions, security controls, live-read verification, or an authorized operation is retained. The controlled EVENT-004 evidence is an evidence-retain case. A historical or synthetic label alone does not remove the always-retain boundary.

### 2.3 Prohibited dry-run behavior

The dry-run must not:

- call Google write methods or Calendar create, update, delete, move, or clear methods;
- edit a Sheet, CalendarLog row, Calendar event, repository file, token, or plugin;
- archive or delete a record, including by a hidden cleanup, migration, or retry path;
- authorize or consume an authorization;
- publish a snapshot, restart a gateway, register a plugin, send Telegram output, or push/merge code;
- treat a successful read, a matching hash, an old timestamp, or a synthetic name as authorization;
- log private evidence or use a private evidence file as a copied report input.

## 3. Policy states

The states below are policy outputs, not operations:

| State | Meaning | Permitted automatic action |
|---|---|---|
| `retain` | Preserve the record and its evidence. The record is protected from archive/delete under this policy. | None |
| `archive-candidate` | A reversible archive may be considered after corroboration and authorization. It is not an instruction to archive. | None |
| `delete-candidate` | Deletion may be considered only after every deletion stop condition passes and separate deletion authorization exists. | None |
| `manual-review` | Evidence is incomplete, ambiguous, stale, contradictory, private, or otherwise requires a human decision. | None |

`manual-review` is the default for unknown or uncertain records. It is not an implicit archive or delete state.

### 3.1 Deny-by-default precedence

Apply the first matching rule in this order; do not allow a lower rule to override a higher one:

1. **Personal or real operational data:** `retain` with `R-PERSONAL-REAL-DO-NOT-TOUCH`.
2. **Required evidence, audit, privacy, security, or authorization evidence:** `retain` with `R-EVIDENCE-RETAIN`.
3. **Known controlled EVENT-004 evidence:** `retain` with `R-EVENT-004-EVIDENCE-RETAIN`.
4. **Contradictory, malformed, partial, inaccessible, or stale input:** `manual-review` with the applicable `M-*` code. If personal/real data is known despite the defect, rule 1 still wins and the result is `retain`.
5. **Unknown classification:** `manual-review` with `M-UNKNOWN-MANUAL-REVIEW`; never archive or delete automatically.
6. **Unreconciled Sheet/Calendar pair:** `manual-review` with `M-PAIR-EXACT-ID-REQUIRED`; never operate on either side of the pair.
7. **Corroborated, non-personal, non-operational, reversible historical material:** `archive-candidate` with `A-CORROBORATED-ARCHIVE-CANDIDATE`, only when all archive gates pass.
8. **Explicitly approved, non-personal, non-operational material with a documented deletion basis and verified restore archive:** `delete-candidate` with `D-EXPLICIT-DELETION-CANDIDATE`, only when all deletion gates pass.
9. **Any other case:** `manual-review` with `M-UNCLASSIFIED-MANUAL-REVIEW`.

The presence of an `archive-candidate` or `delete-candidate` code never authorizes the corresponding operation. If any condition for a candidate is not proven, return `manual-review` instead.

### 3.2 Required special handling

- `EVIDENCE_RETAIN` maps to `retain`; it is not an archive or delete proposal.
- The one `ABANDONED_DRAFT_REVIEW` classification maps to `manual-review` pending corroboration and human authorization. “Abandoned” is not proof that a record is safe to archive or delete.
- `UNKNOWN_MANUAL_REVIEW` always maps to `manual-review`. It must never map to either candidate state through a default or fallback.
- EVENT-003 remains `manual-review`. It may become an `archive-candidate` only after exact corroboration establishes that the record is non-personal, non-operational, no longer needed, and safely reversible, followed by human authorization. It is not a current archive or delete authorization.
- Calendar/Sheet paired records require exact-ID reconciliation before classification can move beyond `manual-review`. A missing, duplicate, mismatched, or unverified pair blocks action on both records.

## 4. Current authoritative inventory and recommendation

The permitted counts-only summary reports 182 records across seven tabs. The two recorded dataset hashes are identical, and five exact CalendarLog event IDs were confirmed in both passes. No mutation is reported or authorized.

| Tab | Records | Classification counts |
|---|---:|---|
| `AuditLog` | 114 | 114 `UNKNOWN_MANUAL_REVIEW` |
| `CalendarLog` | 13 | 1 `ABANDONED_DRAFT_REVIEW`; 1 `EVIDENCE_RETAIN`; 11 `UNKNOWN_MANUAL_REVIEW` |
| `Donations` | 6 | 6 `UNKNOWN_MANUAL_REVIEW` |
| `Inventory` | 7 | 7 `UNKNOWN_MANUAL_REVIEW` |
| `Reports` | 22 | 22 `UNKNOWN_MANUAL_REVIEW` |
| `Requests` | 11 | 11 `UNKNOWN_MANUAL_REVIEW` |
| `Tasks` | 9 | 9 `UNKNOWN_MANUAL_REVIEW` |
| **Total** | **182** | **1 `ABANDONED_DRAFT_REVIEW`; 1 `EVIDENCE_RETAIN`; 180 `UNKNOWN_MANUAL_REVIEW`** |

The current dry-run decision is therefore:

| Proposed state | Count | Decision |
|---|---:|---|
| `retain` | 1 known `EVIDENCE_RETAIN` record, plus any protected evidence/real-data records identified by policy | Preserve; no mutation |
| `archive-candidate` | 0 | No current evidence meets the candidate gates |
| `delete-candidate` | 0 | No current evidence meets the candidate gates; no automatic delete is permitted |
| `manual-review` | 181 classification-marked records | Human review required; no automatic archive/delete |

The `retain` row is a policy minimum from the counts-only classification. Any record independently known to be personal, real operational data, or required evidence remains additionally protected by the precedence rules. Counts in this table are proposals and must not be interpreted as post-operation counts.

Reference integrity for the current summary is recorded without private contents:

- `pass_1` dataset SHA-256: `8b0f8fcca7d5845c0aed5aaa3974dab8f72c000539bfed40677f867706a8919b`;
- `pass_2` dataset SHA-256: `8b0f8fcca7d5845c0aed5aaa3974dab8f72c000539bfed40677f867706a8919b`;
- CalendarLog exact-ID confirmations: 5 in pass 1 and 5 in pass 2.

## 5. Read-only dry-run contract

### 5.1 Inputs

A conforming dry-run accepts an inventory object with this shape. The values shown are types or controlled vocabularies, not an instruction to include private data:

```json
{
  "schema_version": "retention-dry-run/v1",
  "run_ref": "opaque-safe-reference",
  "policy_version": "CLEANUP-007C/v1",
  "source_ref": "opaque-safe-reference",
  "captured_at_utc": "RFC-3339 timestamp",
  "max_age_seconds": 900,
  "passes": [
    {
      "pass_ref": "opaque-safe-reference",
      "dataset_sha256": "64 lowercase hexadecimal characters",
      "tabs": [
        {
          "tab_name": "controlled tab name",
          "row_count": 0,
          "records": [
            {
              "safe_ref": "opaque-safe-reference",
              "row_ordinal": 0,
              "record_sha256": "64 lowercase hexadecimal characters",
              "classification": "controlled classification",
              "pair_ref": "opaque-safe-reference-or-null",
              "pair_status": "EXACT_ID_CONFIRMED|NOT_APPLICABLE|MISMATCH|MISSING|DUPLICATE"
            }
          ]
        }
      ]
    }
  ]
}
```

Input requirements:

- `source_ref`, `run_ref`, `pass_ref`, `safe_ref`, and `pair_ref` are opaque references; raw source IDs and row values are forbidden.
- `record_sha256` is computed over a documented, canonicalized, content-minimized representation and is not a substitute for an opaque reference.
- `row_count` must equal the number of supplied metadata records for that tab; all tab counts must reconcile to the declared total.
- Classifications and pair statuses must be from an allowlist. Unknown fields, missing required fields, duplicate safe references, invalid hashes, or malformed timestamps invalidate the input.
- At least two independent passes are required for a mutation consideration. A one-pass input can report observations but cannot produce an archive/delete candidate.
- The Calendar and Sheet sides of a pair must be reconciled by exact event ID internally by the authorized checker; only the safe pair reference and reconciliation result may appear in dry-run output.

### 5.2 Processing

A conforming dry-run performs these read-only stages in order:

1. **Scope preflight:** verify the approved source reference, policy version, tab allowlist, input schema, and absence of mutation mode.
2. **Freshness check:** reject a snapshot older than `max_age_seconds` (900 seconds by default) as stale. A stale snapshot may not produce a candidate state.
3. **Pass reconciliation:** compare the independent pass hashes, tab counts, classifications, and exact-ID reconciliation summaries. Any difference is `manual-review` with `M-PASS-DATASET-MISMATCH` or the more specific mismatch code.
4. **Privacy check:** verify that only safe references, hashes, counts, controlled statuses, and audit references are present. Any private value or secret is a hard failure; do not continue or print it.
5. **Pair check:** require `EXACT_ID_CONFIRMED` for every applicable Calendar/Sheet pair. Otherwise classify both sides `manual-review` with `M-PAIR-EXACT-ID-REQUIRED`.
6. **Precedence evaluation:** apply section 3.1 exactly once per record. No heuristic, age-only, name-only, or missing-field fallback may produce a candidate.
7. **Report generation:** emit counts and decisions only. Emit an empty `proposed_actions` list for this current inventory.
8. **Independent check:** verify the report without reading private record contents and verify that the dry-run made zero mutations.

### 5.3 Output schema

A conforming output contains only safe references, hashes, counts, and controlled decision data:

```json
{
  "schema_version": "retention-dry-run/v1",
  "run_ref": "opaque-safe-reference",
  "policy_version": "CLEANUP-007C/v1",
  "input_source_ref": "opaque-safe-reference",
  "input_pass_hashes": [
    "64 lowercase hexadecimal characters",
    "64 lowercase hexadecimal characters"
  ],
  "input_total_count": 0,
  "decision_counts": {
    "retain": 0,
    "archive-candidate": 0,
    "delete-candidate": 0,
    "manual-review": 0
  },
  "decision_code_counts": {
    "R-EVIDENCE-RETAIN": 0,
    "A-CORROBORATED-ARCHIVE-CANDIDATE": 0,
    "D-EXPLICIT-DELETION-CANDIDATE": 0,
    "M-UNKNOWN-MANUAL-REVIEW": 0
  },
  "before_counts": {"by_tab": {}, "total": 0},
  "after_counts": {"by_tab": {}, "total": 0, "status": "UNCHANGED|NOT_EXECUTED|INVALIDATED"},
  "reconciliation": {"calendar_exact_id_confirmed": 0, "mismatches": 0},
  "proposed_actions": [],
  "mutation_count": 0,
  "output_sha256": "64 lowercase hexadecimal characters",
  "checker_ref": "opaque-safe-reference",
  "result": "PASS|MANUAL_REVIEW_REQUIRED|INVALID_INPUT|STALE_RECHECK_REQUIRED"
}
```

The actual report may include per-record entries only as `safe_ref`, `record_sha256`, `decision_state`, `decision_code`, and `pair_ref`; it must not include raw record content. `before_counts` are the observed source counts. `after_counts` must equal `before_counts` with status `NOT_EXECUTED` or `UNCHANGED` for a no-mutation dry-run. If a fresh recheck differs, use `INVALIDATED`, do not manufacture after counts, and return `STALE_RECHECK_REQUIRED`.

### 5.4 Deterministic decision codes

The following codes are stable and machine-checkable:

| Code | State | Use |
|---|---|---|
| `R-PERSONAL-REAL-DO-NOT-TOUCH` | `retain` | Personal or real operational data |
| `R-EVIDENCE-RETAIN` | `retain` | Evidence required for accountability, privacy, security, or audit |
| `R-EVENT-004-EVIDENCE-RETAIN` | `retain` | Controlled EVENT-004 evidence |
| `A-CORROBORATED-ARCHIVE-CANDIDATE` | `archive-candidate` | All reversible archive gates passed; authorization still required |
| `D-EXPLICIT-DELETION-CANDIDATE` | `delete-candidate` | All deletion gates passed; deletion authorization still required |
| `M-UNKNOWN-MANUAL-REVIEW` | `manual-review` | `UNKNOWN_MANUAL_REVIEW` input |
| `M-ABANDONED-DRAFT-MANUAL-REVIEW` | `manual-review` | `ABANDONED_DRAFT_REVIEW` input |
| `M-PAIR-EXACT-ID-REQUIRED` | `manual-review` | Calendar/Sheet exact-ID reconciliation absent or failed |
| `M-PASS-DATASET-MISMATCH` | `manual-review` | Independent pass hashes or counts disagree |
| `M-STALE-INPUT` | `manual-review` | Input exceeds freshness limit |
| `M-INVALID-OR-PARTIAL-INPUT` | `manual-review` | Required safe metadata is missing or malformed |
| `M-UNCLASSIFIED-MANUAL-REVIEW` | `manual-review` | No higher-confidence rule matches |

A checker must reject any code/state combination not listed above. Multiple applicable reasons use the highest-precedence state and the most specific code; the report may retain a safe count of secondary blockers without changing the primary decision.

## 6. Freshness, recheck, and paired-record gates

A dry-run is a snapshot, not a standing view of the source. Before any separately authorized archive or delete operation:

1. Re-read the approved source in read-only mode.
2. Recompute the canonical dataset hash and tab counts.
3. Confirm the source is within the 900-second freshness limit.
4. Require exact equality with the dry-run hash and counts, or invalidate the dry-run and start a new one.
5. Reconcile every applicable Sheet record and Calendar event by exact ID; no fuzzy title, date, description, or row-position match is sufficient.
6. Confirm that no new privacy, legal hold, operational, evidence, or authorization constraint exists.
7. Require a new operation-specific authorization after the recheck; a dry-run result cannot be reused as authority.

Any mismatch, timeout, inaccessible source, rate-limit partial result, changed row, changed event, duplicate ID, or missing paired ID stops the operation and yields `manual-review`.

## 7. Archive and rollback requirements

Archiving is permitted only as a later, separately authorized, reversible operation. Before execution, the operator must have:

- exact approved `safe_ref` targets and their record hashes;
- corroboration from the source and an independent read-only check;
- confirmation that the targets are not personal data, real operational data, required evidence, legal-hold material, or an unresolved pair;
- a tested, access-controlled archive destination with retention and access rules;
- a manifest containing only safe references, hashes, source location class, policy version, authorization reference, actor, and timestamps;
- a restore procedure tested against the archived hashes in an isolated target;
- a rollback owner and a stop/restore plan.

The archive operation must be atomic per reconciled pair, preserve the original content and hash under access control, and write an append-only audit entry. If any member of a pair cannot be archived consistently, archive neither member. A failed verification, partial archive, changed hash, or missing audit entry requires immediate stop and rollback where safe. No archive may be treated as deletion.

## 8. Deletion gates and stop conditions

Deletion is exceptional, irreversible, and never automatic. A `delete-candidate` may be reported only after all of the following are proven:

- the target is not personal data or real operational data under the current policy;
- the target is not required evidence, audit history, security evidence, legal-hold material, or an active operational dependency;
- the target is not part of an unresolved Calendar/Sheet pair;
- the source was freshly rechecked and exact target hashes still match;
- a verified, access-controlled, restorable archive exists and its restore check passed;
- the retention basis, deletion reason, scope, actor, and time window are recorded using safe references only;
- the required independent checker passed; and
- separate, explicit deletion authorization was issued by the required approvers for the exact targets.

Stop immediately and make no deletion if any condition is missing or contradictory, if a human asks to stop, if the source changes, if a token or credential appears in output, if a private value is exposed, if a pair does not reconcile, if the archive cannot be restored, if the authorization is expired/reused/ambiguous, or if the operation would exceed its exact scope. A stop is a successful safety outcome, not a partial authorization.

## 9. Audit requirements

Every dry-run and every later authorized operation must produce an append-only audit record containing safe references only:

- policy and schema version;
- run or operation reference;
- source reference and input/output hashes;
- capture and execution timestamps;
- tab and total before/after counts;
- decision and blocker code counts;
- exact safe target references, if any;
- pair-reconciliation result;
- mutation count and operation result;
- independent-checker reference and result;
- authorization reference, approver roles, actor, and expiry for any archive/delete operation;
- rollback or stop outcome, if applicable.

Audit entries must not contain raw rows, event bodies, personal data, secrets, access tokens, or private evidence contents. Failed or stopped attempts are retained as audit evidence; they are not silently removed.

## 10. Approval matrix

| Activity | Policy result | Minimum independent control | Authorization required |
|---|---|---|---|
| Read-only inventory/dry-run | Any state; current run is manual-review/retain only | Independent checker verifies input, precedence, hashes, counts, privacy, and zero mutation | No mutation authorization; operator may run only the approved read-only procedure |
| Retain/do-not-touch | `retain` | Checker verifies protected classification and audit entry | No archive/delete authorization; retention is the default |
| Move to archive | `archive-candidate` | Independent checker plus restore-test evidence | Named data owner/operations approver and privacy approver authorize exact targets and window |
| Delete | `delete-candidate` | Independent checker, verified restore archive, and post-action verification plan | Named data owner/operations approver, privacy approver, and system owner authorize exact targets and window; operator cannot be sole approver |
| Any personal/real operational data | `retain` | Privacy review when scope is uncertain | Separate policy and explicit authorization would be required before any non-retain action |

Role names must resolve to actual authorized humans in the operation record. No inherited, blanket, stale, or reusable authorization is sufficient.

## 11. Independent checker contract

The independent checker must be read-only and independent of the actor preparing a later mutation. For this policy, checker task `t_51a5542e` is the independent verification reference for the CLEANUP-007B counts-only evidence. A future operation requires a fresh checker result for the exact run and exact target scope.

The checker must fail closed and verify:

1. exactly the permitted source summary and safe references were used;
2. no private evidence contents or credentials were read into output;
3. the schema, allowlists, hashes, timestamps, pass equality, tab counts, and total count are valid;
4. classification counts reconcile to 182 current records: 1 `ABANDONED_DRAFT_REVIEW`, 1 `EVIDENCE_RETAIN`, and 180 `UNKNOWN_MANUAL_REVIEW`;
5. CalendarLog exact-ID confirmation counts are 5 in each recorded pass;
6. decision states and codes match the precedence table exactly;
7. `before_counts` and `after_counts` are equal for a no-mutation run, with `proposed_actions=[]` and `mutation_count=0`;
8. no Google write method, archive, delete, edit, publication, gateway, plugin, Telegram, push, or merge action occurred; and
9. the report is within the permitted file scope and passes markdown/privacy checks and `git diff --check`.

A checker failure, missing evidence, or untestable assertion results in `INVALID_INPUT`, `MANUAL_REVIEW_REQUIRED`, or `STALE_RECHECK_REQUIRED`; it must never be converted to `PASS` by omission.

## 12. Current dry-run closeout

Based only on the permitted counts-only summary, this policy records:

- observed inventory: 182 records across `AuditLog`, `CalendarLog`, `Donations`, `Inventory`, `Reports`, `Requests`, and `Tasks`;
- two matching dataset hashes across the recorded passes;
- five exact CalendarLog event IDs confirmed in each pass, without recording those IDs here;
- one evidence-retain classification;
- one abandoned-draft classification requiring manual review;
- 180 unknown classifications requiring manual review;
- zero archive candidates;
- zero delete candidates; and
- zero changes, zero mutation calls, and no authorization to perform any mutation.

This closeout is a policy statement and dry-run recommendation only. It does not assert that a live source is currently unchanged after the recorded snapshot, and it does not authorize any future operation. Any future action must begin with a new read-only inventory, stale-data recheck, exact-ID reconciliation, independent check, and operation-specific human authorization.
