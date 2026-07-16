# Google Reconnect and Cleanup Final Report

**Overall status:** documentation closeout of the checked Google recovery and CLEANUP-007 phases. This report records evidence and limits; it does not authorize a new OAuth attempt, credential write, Google mutation, gateway restart, deployment, publication, push, merge, archive, or delete.

## Overall and current goal

The recovery goal was to restore a guarded, verifiable Google credential path without exposing secrets or mutating unrelated operational data. The cleanup goal was to classify the governed inventory read-only and leave it unchanged unless separately authorized.

The current goal is documentation custody: retain the evidence boundary, record what was independently checked, and make the remaining manual decisions explicit.

## Task graph, profile assignments, and parallel record

- Recovery implementation and repair chain: `5ee7be6`, `da068db`, `797aa6d`, `9996a591`, and final real-Flow redirect integration `dc2ef634c4af117ebfc1c024c9608a257318384d`.
- Independent recovery verdict: GR-CHECK-001, task `t_ed2752a1`, completed PASS at `dc2ef634`.
- Secure inventory verdict: CLEANUP-007B-R2-CHECK, task `t_51a5542e`, completed PASS at `dc2ef634`.
- Credential lifecycle documentation/check: CLEANUP-006C and `t_cdd46aea`, source candidate `5c66afc7395c14f3e80c6599543eba809a35251f`, checker PASS.
- Retention policy/check: CLEANUP-007C and `t_5f852df8`, source candidate `835ca40b0d9b743f5e335e1e2af1176baf1a6762`, checker PASS.
- Integration verdict: `t_aa98a715` completed PASS for clean linear integration at `af2149648b78ae2b05004b632c5b399c4b35d9d9`.

The profile/checker record is evidence of reviewed work, not a standing authorization for any later external action.

## Done

- Redirect, ACL, guarded-candidate, callback-scope, state-comparison, pending-session, explicit-arming, and real-Flow redirect repairs are integrated in the recovery revision.
- One successful callback/exchange is recorded in redacted evidence; no raw callback, code, verifier, authorization URL, token response, client secret, or credential value is reproduced here.
- The candidate was accepted only after the deterministic validation contract reported `ACCEPTED`.
- A reversible Sheets synthetic worksheet lifecycle was completed and removed; the verified post-lifecycle tab counts were restored.
- A Calendar synthetic lifecycle was deleted. Its exact-ID result is one cancelled tombstone and zero active exact-ID matches; a tombstone is not an instruction to recreate the event.
- Guarded promotion used a restricted, same-filesystem rollback backup and post-promotion bounded reads were checked.
- CLEANUP-007B-R2 completed a two-pass read-only inventory with zero mutation.
- CLEANUP-006C and CLEANUP-007C are integrated and independently checked.

## Verified

The following are verified by the completed independent checker records cited above:

- GR-CHECK-001 PASS: redacted recovery evidence, token/backup and ACL checks, focused/full repository tests, and a bounded live Sheets/Calendar read-only probe passed at recovery revision `dc2ef634`.
- The candidate carried the exact eight-scope contract listed below, and the candidate ACL gate matched before acceptance.
- The operational credential remained unchanged until the guarded promotion point; the restricted backup existed for rollback only.
- Post-promotion bounded reads passed. This does not mean every long-lived consumer or gateway process was independently runtime-validated.
- CLEANUP-007B-R2 PASS: 182 records, one abandoned-draft review, one evidence retain, 180 unknown/manual, five confirmed exact Calendar IDs per pass, matching two-pass dataset hashes, and zero mutation calls.
- CLEANUP-006C and CLEANUP-007C checker records passed their source-document scope, privacy, and policy checks.

## Failed and contained history

Historical fixed-port/no-listener redirect handling, candidate ACL mismatch handling, and an earlier Calendar deletion-verifier expectation were repaired or reconciled in the checked recovery chain. They are retained as historical incident evidence only. Legacy insecure URL-evidence artifacts are quarantined/non-authoritative and must not be copied into logs, documentation, or new evidence.

## Current state

- The recovery source is `dc2ef634c4af117ebfc1c024c9608a257318384d`.
- The integrated documentation base before this final report is `af2149648b78ae2b05004b632c5b399c4b35d9d9` (`975fde6` then `af21496`).
- Current retention recommendation: zero changes, zero archive candidates, zero delete candidates, and 180 records requiring manual review.
- The canonical status/index entry is `CLEANUP_MILESTONE_INDEX.md`.

## Blockers and next step

No technical failure is being converted into permission. The remaining blocker is human authorization for any next-wave operation.

Proposed next wave, not approved:

1. obtain a fresh read-only, counts-only inventory and exact-ID reconciliation;
2. obtain human review decisions for the one abandoned draft and the 180 unknown/manual records;
3. design a separately scoped atomic durable-refresh path for the current non-atomic loaders; and
4. isolate and repair the Windows CRLF installer/manifest limitation.

Exact required authorizations before a mutation: named target scope, data-owner/operations approval, privacy approval, system-owner approval for archive/delete, an independent checker, a fresh recheck within its time window, and a tested reversible archive/restore plan where applicable. Gateway/plugin/publication actions require separately named deployment and verification authorization. None is granted by this report.

## Commits

- `5ee7be6df46a020251c2766da4b79e1d72d36824` — OS-assigned loopback port repair.
- `da068dbc5a5cafc1f270e765fc53881750d17f2d` — constant-time state comparison.
- `797aa6d6c6975d4e6ac2ad254b48ee5e6297b87c` — exact callback-scope validation.
- `9996a59105df3e90f42bc63f408925f8342187e6` — explicit runner arming.
- `dc2ef634c4af117ebfc1c024c9608a257318384d` — real OAuth Flow redirect contract.
- `975fde6` — integrated credential lifecycle closeout.
- `af2149648b78ae2b05004b632c5b399c4b35d9d9` — integrated record-retention policy.

## Tests and checkers

Recorded successful gates include:

- GR-CHECK-001: focused runner tests, full suite, compile checks, redacted evidence validation, ACL/hash checks, and a bounded read-only Sheets/Calendar probe.
- CLEANUP-007B-R2-CHECK: strict non-printing evidence-schema/reconciliation validation; inventory/ACL tests; full suite recorded as 209 passed and 64 subtests passed at its recovery revision.
- Integration checker `t_aa98a715`: focused runtime/drift/install/behavior parity suite recorded as 10 passed; strict drift passed; full suite recorded as 209 passed and 64 subtests passed; tracked source parity passed.

The direct installer dry-run is a known exception: on this Windows checkout it exits 2 on a CRLF-versus-LF manifest comparison. The checker established that tracked canonical blobs match their manifest hashes; no installer write was performed. The exception remains a limitation, not a PASS claim.

## Redirect decision

The installed-app recovery path binds IPv4 loopback on `127.0.0.1` with port `0`, forms one canonical root-path redirect from the live listener, and requires that same literal value through authorization, callback, and exchange. Missing, fixed-port, mismatched, noncanonical, expired, or malformed callback paths fail closed before exchange. The real `Flow` redirect is validated against the canonical listener redirect before URL construction or fetch.

## Exact scopes

The checked contract has exactly these eight source-defined scopes:

1. `https://www.googleapis.com/auth/gmail.readonly`
2. `https://www.googleapis.com/auth/gmail.send`
3. `https://www.googleapis.com/auth/gmail.modify`
4. `https://www.googleapis.com/auth/calendar`
5. `https://www.googleapis.com/auth/drive`
6. `https://www.googleapis.com/auth/contacts.readonly`
7. `https://www.googleapis.com/auth/spreadsheets`
8. `https://www.googleapis.com/auth/documents`

No scope reduction, re-consent, or change to this set is authorized here.

## Candidate

Candidate validation is deterministic and fail-closed. The accepted result required identity/serialization checks, exact scope equality, refresh-token presence, unchanged operational baseline until promotion, and candidate ACL equivalence. The recorded invariant code is `ACCEPTED`; acceptance was not an operational overwrite by itself.

## Sheets lifecycle

The checked synthetic worksheet lifecycle covered create, write, read, update, read, and delete. It was reversible: the worksheet was removed and the verified tab counts were restored. This does not authorize a future worksheet mutation or a broader Sheets cleanup.

## Calendar lifecycle

The checked synthetic Calendar lifecycle covered create, read, update, read, and delete. Google Calendar retained a cancelled tombstone for the exact event identity while an active exact-ID check returned zero. The reconciliation criterion is zero active exact-ID matches, not a demand for a 404/410 response and not a request to recreate the cancelled event.

## Promotion and rollback

The recovery-only promotion helper validates candidate and operational prerequisites before mutation, uses a restricted same-filesystem backup, replaces atomically, verifies the promoted ACL, and restores on failure. The temporary backup is removed after success; it is rollback-only, not a retained archive. Current application credential loaders are different: their durable refresh writes are direct and non-atomic. They remain a separate hardening task.

## Inventory

See `CLEANUP_007B_RECORD_INVENTORY_SUMMARY.md` for the counts-only result: 182 records, one abandoned-draft review, one evidence retain, 180 unknown/manual, five exact Calendar IDs confirmed per pass, and zero mutation. The active plan authorizes zero changes.

## Evidence

Only safe, redacted/counts-only artifact references and fingerprints are retained here:

- `C:/Users/fallo/AppData/Local/Temp/GR_OAUTH_002_EXCHANGE_RESULT.json` — SHA-256 `f624711c04e8987228580e012220d9625e023a6ee825668b0f3d4aff833cba66`.
- `C:/Users/fallo/AppData/Local/Temp/GR_OAUTH_003_CANDIDATE_ACCEPTANCE.json` — SHA-256 `c1df2237229920683860cf2cc7fd711226eb8841b9c33883186ea0ddd7792be5`.
- `C:/Users/fallo/AppData/Local/Temp/CLEANUP_007B_LIVE_INVENTORY_SUMMARY_R2.json` — SHA-256 `78c81a5591d0fe710a2acbaff7dbb76a1c15e0e30cf5c1cf82fc08c84cfcc1fb`.

These fingerprints do not authorize disclosure of underlying content. Private inventory evidence and credential material are deliberately excluded.

## Limitations

- The gateway was not restarted or independently runtime-validated.
- No plugin deployment, publication, push, merge, archive, or delete was performed or authorized.
- Current loaders remain non-atomic for durable refresh.
- In-memory refresh was verified for bounded read-only inventory only; it left the token file unchanged and is not proof of durable-refresh safety.
- The installer dry-run limitation remains: Windows CRLF checkout bytes can fail the direct manifest check even while tracked blobs, tests, and strict drift pass.
- The 180 unknown/manual records require human review. The current retention plan authorizes zero changes.

This is a final report of completed evidence and known limits. It intentionally makes no final phase PASS claim; independent checker approval remains the final decision.
