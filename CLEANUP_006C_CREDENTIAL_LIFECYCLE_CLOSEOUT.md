# CLEANUP-006C — Credential Lifecycle Closeout

**Status:** documentation-only lifecycle closeout.

**Authorized repository write:** this file only.

**No live action in this task:** no Google/OAuth request, token refresh, candidate creation, promotion, token-file write, ACL mutation, gateway restart, plugin change, publication, push, or merge was performed. This report does not contain credential values, authorization codes, client secrets, raw callbacks, generated authorization URLs, token responses, resource identifiers, or raw ACL output.

## Evidence labels

- **VERIFIED** means directly supported by the cited repository source, the named redacted evidence artifact, or the parent independent-checker handoff.
- **INFERRED** means a constrained conclusion from verified source/evidence; it is not a fresh runtime observation.
- **PROPOSED** is a required future procedure, not current behavior or approval.
- **UNTESTED** means this task did not run the live operation or inspect the external runtime needed to establish it.

## System model and boundaries

| Concern | Owner and boundary |
|---|---|
| Operational credential | The external authorized-user JSON used by `scripts/non_profit_hermes_ops.py` and `scripts/sync_approved_safe_data.py`; it is durable state and is outside this repository. |
| Candidate credential | A separate, restricted candidate path in the guarded recovery design; it must remain separate from the operational path until explicit promotion. |
| OAuth attempt state | The guarded recovery design persists only a restricted pending record: canonical redirect, state, verifier, and expiry. Listener/socket objects, browser objects, raw callback query, handoff URL, and generated response pages are runtime-only. |
| Runtime credentials/services | Per-call Python `Credentials` and Sheets/Calendar service objects. They are derived runtime state, not durable credential state. |
| Remote durable data | Google Sheets and Google Calendar. The only repository-integrated Google services found in the current worktree are Sheets v4 and Calendar v3. |
| Derived data | Approved-safe `/daily` snapshot and explicit public-site export data; neither is credential state. |

**Invariant:** validation happens before mutation of the operational credential. A failed candidate, failed refresh, failed callback, failed ACL comparison, or failed serialization must leave the operational credential unchanged. Rendering/logging must receive only fixed diagnostic codes, booleans, counts, or approved hashes.

## Reconciled lifecycle status

### 1. Historical expired-token failure and protected baseline

- **VERIFIED (supplied recovery premise):** the recovery sequence began after the old operational token could not be refreshed. This closeout does not re-run or inspect that failed refresh.
- **VERIFIED (redacted evidence):** `C:/Users/fallo/AppData/Local/Temp/GR_OAUTH_002_EXCHANGE_RESULT.json` records a PASS, one attempted exchange, accepted completion, no raw callback/code/token-response recording, and a pre-promotion operational baseline fingerprint. `C:/Users/fallo/AppData/Local/Temp/GR_OAUTH_003_CANDIDATE_ACCEPTANCE.json` records a PASS/accepted candidate assessment against the same pre-promotion baseline fingerprint and records no credential values.
- **VERIFIED (source):** the guarded runner captures an operational baseline hash before its flow and checks it before and after the one exchange/candidate preparation path (`scripts/google_oauth_live_runner.py` at recovery revision `dc2ef634c4af117ebfc1c024c9608a257318384d`, lines 247–267 and 361–400).
- **INFERRED:** the unchanged baseline recorded before both exchange and acceptance, combined with the runner's before/after guard, supports the conclusion that candidate acceptance did not silently overwrite the operational credential.
- **UNTESTED:** this task did not repeat the old refresh failure or compare the actual operational file bytes after an actual promotion. It therefore does not claim a live credential replacement occurred.

### 2. Candidate ACL mismatch, Windows repair, and candidate acceptance

- **VERIFIED (source):** the candidate acceptance evaluator rejects `CANDIDATE_ACL_MISMATCH` before `ACCEPTED` and also requires identity match, exact granted scopes, refresh-token presence, valid/expected serialization, expected token type, and unchanged existing token (`scripts/google_oauth_candidate_acceptance.py:27–39, 92–114`). It accepts only derived metadata and performs no I/O.
- **VERIFIED (source):** the Windows ACL repair module writes a candidate, enables inheritance on that newly created file with `icacls /inheritance:e`, compares path-independent semantic ACL snapshots, deletes the candidate on mismatch/failure, and reports redacted failures (`google_oauth_acl.py` at `dc2ef634`, lines 111–142). A semantic mismatch is therefore fail-closed rather than accepted because formatted `icacls` text happens to look similar.
- **VERIFIED (test/source):** the ACL tests cover a true-rights mismatch, candidate cleanup on mismatch, semantic equivalence success, and a Windows-local synthetic proof when `icacls` is available (`tests/test_google_oauth_acl.py` at `dc2ef634`, lines 52–96).
- **VERIFIED (redacted evidence):** the candidate-acceptance artifact reports accepted status, eight scopes, no credential-value recording, and a successful candidate-ACL check. No ACL principals or raw ACL descriptors are reproduced here.
- **INFERRED:** the historical candidate ACL mismatch was repaired by the guarded candidate-preparation path before the accepted diagnostic was emitted. The report intentionally does not reproduce the original unsafe ACL output.
- **UNTESTED:** this task did not invoke `icacls` on any operational or candidate credential and did not create/repair a credential file.

### 3. Redirect incident and installed-app loopback repair

- **VERIFIED (forensic report):** `CLEANUP_006B_R4L_REDIRECT_FORENSIC_REPORT.md` records the historical fixed `localhost` port-1 helper failure as `REDIRECT_URI_NOT_CONFIGURED`, with no exchange endpoint contact. It classifies the client as an installed application and records no live Console change.
- **VERIFIED (architecture/source):** the repair freezes a one-shot IPv4 loopback listener on `127.0.0.1`, requests OS port `0`, forms the canonical root-path redirect from the bound listener, and requires the same literal redirect through authorization, callback, and exchange. See `CLEANUP_006B_R4L_REDIRECT_DECISION.md` at preserved revision `25fd929fb640b19df7ccec9cca4dbf6f95f904b7` and `scripts/google_oauth_redirect.py` at recovery revision `dc2ef634`.
- **VERIFIED (source):** invalid/noncanonical redirect values, fixed-port requests, mismatched host/port/path/trailing slash, later callbacks, missing code, provider errors, and listener expiry return redacted terminal codes and cannot reach exchange.
- **INFERRED:** replacing manual fixed-port copy-back with a listener that first binds an OS-selected loopback port removes the historical fixed-port/no-listener failure class without changing the installed-app client family.
- **UNTESTED:** no live browser, Google Console, firewall, or provider acceptance check was run by this task.

### 4. Exchange-order and state/callback guards

The recovered source below is preserved at `dc2ef634` on `cleanup-007a`; it is not represented as merged into this documentation worktree (`cleanup-006b-r2d`). The distinction is intentional.

- **VERIFIED:** state and PKCE verifier are generated per attempt with cryptographic `secrets.token_urlsafe` factories in the guarded runner. Tests inject deterministic factories without changing production randomness order.
- **VERIFIED:** the listener is bound before the redirect exists, and the pending session is saved before authorization construction. A failed pending save blocks authorization construction and exchange; terminal cleanup clears pending state and closes the listener. Recovery revisions `f2ae477` and `dc2ef634` source/test history establish this order.
- **VERIFIED:** persisted state/verifier and callback state comparisons use `hmac.compare_digest` after strict type/shape checks (`da068db` source history). No callback-provided state can overwrite expected state.
- **VERIFIED:** callback scopes are parsed once into a duplicate-free canonical set and must exactly equal the requested immutable scope set before exchange. Missing, partial, extra, duplicate, malformed, or multiple scope parameters fail with no exchange (`797aa6d` source/test history).
- **VERIFIED:** `GoogleAuthFlowAdapter.from_client_secret` supplies the listener's exact redirect to the real `Flow.from_client_secrets_file`; the adapter validates that the underlying real `Flow.redirect_uri` equals it before URL construction or fetch. It does not invent non-existent authorization/exchange attributes on the real Flow object (`dc2ef634`, runner lines 286–348).
- **VERIFIED:** the explicit CLI runner is fail-closed unless `--execute-live`, an exact operational baseline hash, valid timeout/TTL, and a fresh Temp evidence output are supplied. Help/non-live/malformed paths do not dispatch the runner (`9996a591` source/test history).
- **VERIFIED (redacted evidence):** the exchange artifact records exactly one attempted exchange and accepted completion; it records no raw callback, authorization code, or token response.
- **UNTESTED:** this task did not execute the armed runner and does not authorize another exchange.

### 5. Candidate validation, Sheets/Calendar read validation, and tombstones

- **VERIFIED:** candidate acceptance is redacted and deterministic. It rejects broader or narrower scope sets and evaluates a stable first-failure order without carrying credential material (`CLEANUP_006_OAUTH_ACCEPTANCE_DIAGNOSTICS.md`, sections 2–4).
- **VERIFIED (parent independent checker handoff):** secure R2 inventory evidence at `cleanup-007a` passed strict private-schema/reconciliation validation, ACL-equivalence verification, and focused/full test gates. The checker confirmed no Google write-method calls in the R2 inventory runner and identified its bounded read chain as Sheets `values.batchGet` plus Calendar `events.get`; the runner refreshes credentials only in memory for bounded read-only work.
- **VERIFIED (current worktree source):** approved-safe calendar export is read-only relative to Sheets/Calendar mutation and excludes absent, stale, or cancelled live event IDs. It builds the live status map from Calendar list results and suppresses rows whose event status is `cancelled` (`scripts/sync_approved_safe_data.py:520–579`). `tests/test_event_calendar_privacy.py:212–224` proves a cancelled tombstone is not exported.
- **INFERRED:** a reversible validation must preserve the operational credential and remote Sheets/Calendar data while it collects only bounded read results; a cancelled event is a tombstone/non-public result, not a reason to recreate it.
- **UNTESTED:** this task did not perform a new Sheets/Calendar read, compare remote contents before/after, or independently reproduce the R2 inventory. The checker explicitly noted it validated completed two-pass evidence rather than overwriting it with a fresh run.

### 6. Promotion, backup, rollback, and post-promotion verification

**Current loader limitation**

- **VERIFIED:** neither current-worktree credential loader is transactional. `non_profit_hermes_ops.get_creds()` directly rewrites the token after refresh; `sync_approved_safe_data.creds()` directly rewrites only when `persist_refresh=True` (`scripts/non_profit_hermes_ops.py:124–129`; `scripts/sync_approved_safe_data.py:110–117`). They do not create a temp file, atomically replace, preserve/reset ACLs, keep a backup, or roll back.
- **VERIFIED:** this report must not call either current loader atomic.

**Guarded promotion implementation**

- **VERIFIED (separate recovery source):** `google_oauth_acl.atomic_promote` at `dc2ef634` requires both paths to be regular files on the same filesystem and requires candidate/operational semantic ACL equality before mutation.
- **VERIFIED (separate recovery source):** it creates an empty backup name in the operational file's parent directory, atomically moves operational to that backup with `os.replace`, atomically moves candidate into the operational path, then verifies the promoted ACL. The backup originates from the already restricted operational file, so restriction is retained by rename; this is not a copy to an uncontrolled directory.
- **VERIFIED (separate recovery source):** if candidate replacement or promoted-ACL verification fails, it moves any partial operational file back to candidate as needed and restores the backup to the operational path. A failed restoration is surfaced as `ROLLBACK_FAILED`. On success it deletes the temporary backup, so it is a rollback-only backup rather than a retained recovery archive.
- **VERIFIED (tests):** synthetic tests prove success, injected candidate-replacement rollback, and promoted-ACL-mismatch rollback (`tests/test_google_oauth_acl.py:99–155` at `dc2ef634`).
- **PROPOSED:** a separately authorized live promotion must add a protected, durable operator recovery copy if retention beyond the swap is required; the tested helper's success path removes its temporary rollback backup.
- **PROPOSED:** after a separately approved promotion, run a new process/read that loads the selected operational path, validates serialization/client identity/exact scope set/refresh-token presence/ACL, performs only the approved read validation, and obtains an independent PASS before enabling writes.
- **UNTESTED:** no live promotion, post-promotion process read, or independent post-promotion PASS was performed by this task. The PASS artifacts in this report prove accepted candidate/exchange and separately checked R2 inventory; they are not a claim of a completed operational-token promotion.

## Future access-token expiry procedure

- **VERIFIED:** access-token expiry is normal OAuth lifecycle behavior. The existing loaders first use the refresh token when `expired and refresh_token` is true.
- **PROPOSED:** normal expiry must first attempt refresh; it does not itself require fresh consent. Fresh consent/reconnect is a stop condition only when refresh fails, the refresh token is absent/revoked, the client/scope contract is incompatible, or validation rejects the refreshed/candidate state.
- **PROPOSED:** on refresh failure, preserve the operational credential file exactly; return a redacted failure, retain no candidate/pending/handoff artifact, and do not construct a substitute credential.
- **VERIFIED:** `/daily` calls `approved_safe_sync.creds(persist_refresh=False)` and builds its result from an in-memory approved-safe snapshot (`scripts/telegram_intake_router.py:2337–2358`). The R2 inventory checker independently reported in-memory refresh only for its bounded read-only flow.
- **PROPOSED:** bounded read-only work may refresh only in memory. It must not rewrite the operational credential, alter Sheets/Calendar, or use the refresh as proof that durable state is safe.
- **PROPOSED:** a durable refreshed credential requires all of the following before a write: semantic ACL equivalence; valid serialization and expected shape; matching client identity; the exact eight-scope set below; refresh-token presence; an unchanged operational baseline until the explicit promotion point; same-filesystem atomic replacement; rollback on every failed promotion phase; and a clean post-replacement read by a newly constructed consumer.

### Exact current repository-safe scope set

**VERIFIED:** both current credential loaders declare this same eight-item set. Scope names are source constants, not credential values or proof that a live token currently carries every grant.

1. `https://www.googleapis.com/auth/gmail.readonly`
2. `https://www.googleapis.com/auth/gmail.send`
3. `https://www.googleapis.com/auth/gmail.modify`
4. `https://www.googleapis.com/auth/calendar`
5. `https://www.googleapis.com/auth/drive`
6. `https://www.googleapis.com/auth/contacts.readonly`
7. `https://www.googleapis.com/auth/spreadsheets`
8. `https://www.googleapis.com/auth/documents`

No scope reduction or re-consent is authorized by this documentation task.

## Gateway and process reload determination

- **VERIFIED (repository source):** `telegram_intake_router.services()` calls `ops.get_creds()` and creates Sheets/Calendar clients on each call (`scripts/telegram_intake_router.py:858–860`). `daily_services()` likewise calls `approved_safe_sync.creds(persist_refresh=False)` and constructs new service clients (`scripts/telegram_intake_router.py:2337–2340`). The inspected source has no module-level cached `Credentials` or service client for these paths.
- **INFERRED:** a later service invocation through these functions reloads credential state from the selected file. Any credential/service already constructed for an in-flight operation remains that operation's runtime object and is not retroactively replaced.
- **UNTESTED:** the external Hermes gateway/process launcher, installed runtime plugins, and live process lifetime were not inspected in this task. Therefore a gateway restart is neither claimed required nor claimed unnecessary. A separately authorized promotion must verify the actual deployment's credential-loading/caching boundary and use a controlled restart/reload only if that process demonstrably caches credentials.

## Evidence inventory and quarantine rule

**Repository/source references**

- `CLEANUP_006_OAUTH_STATIC_INVENTORY.md`
- `CLEANUP_006_OAUTH_THREAT_MODEL.md`
- `CLEANUP_006_OAUTH_ACCEPTANCE_DIAGNOSTICS.md`
- `CLEANUP_006B_R4L_REDIRECT_FORENSIC_REPORT.md`
- Preserved recovery source/test revisions: `894580b`, `f2ae477`, `da068db`, `797aa6d`, `9996a591`, and `dc2ef634`.

**Redacted external evidence references**

- `C:/Users/fallo/AppData/Local/Temp/GR_OAUTH_002_EXCHANGE_RESULT.json`
- `C:/Users/fallo/AppData/Local/Temp/GR_OAUTH_003_CANDIDATE_ACCEPTANCE.json`
- `C:/Users/fallo/AppData/Local/Temp/CLEANUP_007B_R2_RUNNER.py`
- `C:/Users/fallo/AppData/Local/hermes/CLEANUP_007B_LIVE_INVENTORY_PRIVATE_R2.json`
- `C:/Users/fallo/AppData/Local/Temp/CLEANUP_007B_LIVE_INVENTORY_SUMMARY_R2.json`

- **VERIFIED (parent checker):** the R2 runner, private evidence, and redacted summary were present with verified hashes; the independent check passed the no-write/read-only and reconciliation gates. The private record was not printed by the checker.
- **QUARANTINED / NON-AUTHORITATIVE:** legacy failed/insecure Temp URL-evidence artifacts matching `GR_OAUTH_001_URL_EVIDENCE*.json` are not used to authorize exchange, acceptance, promotion, reload, or release. They must not be copied into repository history, logs, chat, or public evidence; this report intentionally omits their content and any raw URL.
- **UNTESTED:** no Temp artifact establishes Google Console state, gateway reload state, or a completed operational-token promotion.

## Closure checklist

- [x] Historical refresh failure is recorded without re-running it or exposing credential material.
- [x] Candidate acceptance, ACL gate, baseline protection, one-exchange evidence, and exact-scope contract are reconciled with labels.
- [x] Fixed port redirect failure and installed-app port-0 loopback repair are reconciled with labels.
- [x] Constant-time state, pending-before-URL, exact callback scopes, real Flow redirect validation, and explicit runner arming are documented.
- [x] Read-only Sheets/Calendar validation and cancelled tombstone semantics are documented without claiming a new live read.
- [x] Current direct-refresh persistence is explicitly not called atomic; guarded-promotion rollback semantics and their retention limit are documented.
- [x] Gateway reload uncertainty is explicit.
- [x] Failed insecure Temp evidence is quarantined and non-authoritative.
- [x] No secret value, raw callback, generated authorization URL, or token response is included.
