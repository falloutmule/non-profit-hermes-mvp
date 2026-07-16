# CLEANUP-006B — Google Credential Decision Packet (R3)

**Status:** Decision-ready; documentation-only handoff
**Scope:** This packet is the single authorized file for this task: `CLEANUP_006B_GOOGLE_CREDENTIAL_DECISION_PACKET.md`. No source, credential, runtime, plugin, deployment, or release file is changed by this packet.

## 1. Decision and release boundary

### Accepted offline integration

The offline integration is accepted at the following supplied revisions:

- **Worktree HEAD:** `52bbfe0b1a1b35f1ff489b73f8ec31e9828dea73`
- **`main`:** `72959e44a62b413b1ea5d85d4cd83cb3dccc530d`

This acceptance is offline and source-based. It is not evidence that Google authorization, credential rotation, a live probe, gateway restart, deployment, or publication occurred.

### Required boundary statements

- **CLEANUP-007B remains held.** Nothing in this packet authorizes, starts, or releases CLEANUP-007B.
- No OAuth URL was generated.
- No Google endpoint was contacted.
- No credential file was accessed, inspected, changed, refreshed, replaced, or promoted.
- No token, candidate token, auth code, client secret, or raw credential content is included here.
- No gateway was restarted; no plugin was deployed; nothing was published or released.
- No commit, push, or merge was performed or authorized.
- CRLF/path recovery is closed for this handoff: the intended repository/worktree path is `C:\Users\fallo\non-profit-hermes-mvp\worktrees\nonprofit-cleanup-records`, and the authorized artifact is the single Markdown file named above. No alternate path, line-ending repair, or recovery write is part of this task.

The existing token facts referenced by the handoff are **historical supplied state only**. They were not re-checked by this task.

## 2. Executive decision

**Recommendation: Option B — one minimum operational credential** with exactly these intended Google API scopes:

- `https://www.googleapis.com/auth/spreadsheets`
- `https://www.googleapis.com/auth/calendar.events`

This is a recommendation for a future, separately authorized credential change—not an authorization to perform it. It matches the observed normal-operation write paths while removing unrelated Gmail, Drive, Contacts, and Docs access. It is simpler to operate than two credentials and fits the current approval gates: Sheets writes are the controlled record system; Calendar insertion is gated by an explicitly approved, ready event draft and one-shot local authorization at the router boundary.

**Important implementation constraint:** the current code hardcodes the broad eight-scope helper in both operational scripts. Option B cannot be safely selected in the running code without a code change outside this documentation task. Option C is likewise not safely selectable without a code change that explicitly separates credential loading/service construction and selects the correct credential per operation. Therefore this packet recommends Option B as the least-privilege target state, while keeping the current broad helper unchanged and rejecting any live credential action until an approved implementation change exists.

## 3. What the code actually integrates

### Credential loading and service construction

The two Google-integrating scripts use the same local token path and the same broad scope list:

- `scripts/non_profit_hermes_ops.py:56-69` defines the repository root, local token path, eight broad scopes, and the spreadsheet/calendar identifiers. The identifiers are intentionally **not reproduced here**; they are classified as the canonical workbook and operations-calendar resources.
- `scripts/non_profit_hermes_ops.py:124-129` loads authorized-user credentials and silently refreshes an expired credential when a refresh token exists, then writes the refreshed serialized credential back to the token path.
- `scripts/non_profit_hermes_ops.py:132-137` constructs Sheets v4 and Calendar v3 clients.
- `scripts/sync_approved_safe_data.py:44-59` duplicates the same local token path, broad scopes, and canonical workbook/calendar identifiers.
- `scripts/sync_approved_safe_data.py:110-125` loads credentials, optionally persists a refresh, and constructs Sheets v4 and Calendar v3 clients.

The source contains a write-capable Sheets scope and broad Calendar scope today; the code does not currently implement an Option A/B/C selector or distinct cleanup/operational credential paths.

### Spreadsheet read and cleanup/export behavior

- `scripts/non_profit_hermes_schema.py:247-254` defines header ranges and the full used range as `TAB!A:<last-schema-column>`; this is a full-column, all-row read model.
- `scripts/sync_approved_safe_data.py:128-134` implements `read_sheet_rows`, calling `spreadsheets.values.get` against that canonical full range.
- `scripts/sync_approved_safe_data.py:736-757` collects all governed tabs into an in-memory snapshot, applies safe export gates, and does not write files during collection.
- `scripts/sync_approved_safe_data.py:780-789` defines the explicit sync: `--dry-run` reads and reports metrics; normal sync writes the approved-safe public site only after collection.
- `scripts/sync_approved_safe_data.py:288-335` defines dry-run metrics, including rows read, post-row-100 rows, approved/rejected counts, duplicate counts, board-log aggregate count, and `filesystem_writes: 0`.
- `scripts/sync_approved_safe_data.py:760-777` is the publication writer. It writes approved JSON/pages only on the explicit non-dry-run path. It does not establish consent by itself; the per-record gates in the safe functions are the relevant controls.

The public preview/publication boundary is deny-by-default:

- Requests require approved privacy, public status, affirmative `ConsentToShare`, and a nonempty need description (`scripts/sync_approved_safe_data.py:340-373`).
- Donations require approved privacy, public status, affirmative `PublicListingAllowed`, and a nonempty item description (`scripts/sync_approved_safe_data.py:376-407`).
- Reports require approved privacy, public status, affirmative `PublicSummaryAllowed`, and a nonempty `PublicSummaryDraft` (`scripts/sync_approved_safe_data.py:410-440`).
- Calendar publication requires a live event ID, approved privacy, affirmative `PublicCalendarAllowed`, approval `approved` or `created`, status `confirmed` or `ready`, a public title, and a live non-cancelled Calendar event (`scripts/sync_approved_safe_data.py:520-579`).
- `scripts/sync_approved_safe_data.py:611-731` builds board-facing preview pages from already-filtered data; it does not expose private intake fields in those page bodies.
- `scripts/telegram_intake_router.py:2337-2347` creates read-only service clients for `/daily`, with `persist_refresh=False`, and builds the summary from an in-memory approved-safe snapshot.
- `scripts/telegram_intake_router.py:2361-2423` shows `/daily` behavior: today’s approved-safe events, urgent requests, donations, reports, follow-ups, and a website-link summary; inventory is explicitly not public and sensitive items remain for private review.

### Record inventory and governed tabs

The canonical schema governs exactly seven tabs, including `AuditLog`:

1. **Requests** — primary key `RequestID`
2. **Donations** — primary key `DonationID`
3. **Reports** — primary key `ReportID`
4. **Tasks** — primary key `TaskID`
5. **Inventory** — primary key `ItemID`
6. **CalendarLog** — primary key `EventDraftID`; `CalendarEventID` identifies a promoted live event
7. **AuditLog** — primary key `AuditID`

Evidence: `scripts/non_profit_hermes_schema.py:21-178` defines all headers; `scripts/non_profit_hermes_schema.py:183-191` defines primary keys; `scripts/non_profit_hermes_schema.py:304-314` defines deterministic tab order. `AuditLog` fields include actor, action, target, before/after, result, error, and source link (`scripts/non_profit_hermes_schema.py:166-178`).

### Sheets write functions and approval/normal-operation relationships

`non_profit_hermes_ops.py` is an operational write backend, not a cleanup-only reader:

- Requests: `add_request` and `update_request` (`scripts/non_profit_hermes_ops.py:226-358`) check/request by `RequestID`, append or update rows, and write an audit row.
- Donations: `add_donation` and `update_donation` (`scripts/non_profit_hermes_ops.py:361-504`) ensure headers, deduplicate by `DonationID`, append/update, and audit.
- Reports: `add_report` and `update_report` (`scripts/non_profit_hermes_ops.py:507-633`) ensure headers, append/update, and audit.
- Tasks: `add_task` and `update_task` (`scripts/non_profit_hermes_ops.py:636-743`) ensure headers, deduplicate by `TaskID`, append/update, and audit.
- Inventory: `update_inventory` (`scripts/non_profit_hermes_ops.py:746-842`) upserts by `ItemID`, updating an existing row or appending a new row, then audits.
- Common Sheets writes: `append_row` and `ensure_header` (`scripts/non_profit_hermes_ops.py:142-170`) use `values.append` and `values.update`; `write_audit_log` appends to `AuditLog` (`scripts/non_profit_hermes_ops.py:173-203`).

These functions are normal operational record writes. The public-export approval gates do not make private operational writes read-only; they govern which selected fields may be exported publicly. The event-specific approval gate is stricter and explicit, described below.

### Calendar list, insert, and idempotency

- `_calendar_event_exists` lists the canonical operations calendar with a title query and returns a matching event ID (`scripts/non_profit_hermes_ops.py:105-119`).
- `_insert_google_calendar_event` calls `events.insert` on the canonical calendar (`scripts/non_profit_hermes_ops.py:845-868`).
- `create_calendar_event` checks for an existing same-title event before insertion, inserts once, appends one `CalendarLog` row, and audits (`scripts/non_profit_hermes_ops.py:871-935`).
- Draft creation/update is Sheet-only and keyed by `EventDraftID`; `upsert_event_draft` preserves one draft row and leaves `CalendarEventID` blank during draft work (`scripts/non_profit_hermes_ops.py:979-1101`).
- `update_event_draft` is a strict existing-row update and preserves the live event ID (`scripts/non_profit_hermes_ops.py:1104-1201`).
- `create_calendar_event_from_draft` blocks unless the draft exists, has no event ID, has valid offset-aware times, `ApprovalStatus=approved`, and `Status=ready`; it then inserts once and updates the same `CalendarLog` row (`scripts/non_profit_hermes_ops.py:1242-1349`). If `CalendarEventID` is already populated, it returns `already_created` without another insert (`scripts/non_profit_hermes_ops.py:1263-1284`).
- The router is draft-first: `scripts/telegram_intake_router.py:1872-1878` states that `/event` writes a Sheet-only draft and does not create a Calendar event unless creation is explicitly enabled and the draft is promoted. The live-plugin default supplied for this handoff is `allow_calendar_creation=False`.
- The router’s one-shot local authorization constants and validation are at `scripts/telegram_intake_router.py:30-34` and `scripts/telegram_intake_router.py:193-253`; it binds authorization to one draft, one source scope, an expiry, and one remaining use. This is an application approval gate, not a substitute for least-privilege OAuth scopes.

**Capability limit:** no Calendar delete, event-update, calendar-admin, ACL, or sharing code path is required or implemented in the inspected integration. Calendar event update/delete must **not** be inferred merely because a scope could permit it. The observed Calendar operations are list/search and insert, plus Sheet-side draft/status updates.

### Absence of unrelated service paths

Static inspection of the cited integrations found no Drive, Gmail, Contacts, Docs, Calendar ACL, or Calendar sharing API calls. Their names appear in the current broad helper scope list (`scripts/non_profit_hermes_ops.py:58-67`; `scripts/sync_approved_safe_data.py:48-57`), but the reviewed code constructs only Sheets v4 and Calendar v3 clients (`scripts/non_profit_hermes_ops.py:132-137`; `scripts/sync_approved_safe_data.py:120-125`) and uses no unrelated service constructor or endpoint. This absence is a code observation, not a claim that the broad grant is harmless.

## 4. Scope options and decision matrix

| Option | Intended scopes | What it supports | Advantages | Blocking limitation / decision |
|---|---|---|---|---|
| **A — cleanup-only read-only** | `https://www.googleapis.com/auth/spreadsheets.readonly` + `https://www.googleapis.com/auth/calendar.readonly` | Full-range Sheets reads, Calendar list/read, dry-run, `/daily`, bounded no-mutation probes | Strongest least privilege for cleanup; no write capability | Does not support observed normal-operation Sheets appends/updates or Calendar inserts. **Reject as the single credential for this integrated system; viable only for a genuinely separate read-only cleanup job.** |
| **B — one minimum operational credential** | `https://www.googleapis.com/auth/spreadsheets` + `https://www.googleapis.com/auth/calendar.events` | Observed Sheets record/audit writes, Calendar list/read needed by duplicate checks and export, and Calendar event insertion | Least privilege that covers current normal operation; one credential is simpler to select, monitor, back up, and roll back; aligns with current approval gates | Requires a future code change because current code hardcodes the broad helper. **Recommended target state, not authorized implementation.** |
| **C — separate cleanup and operational credentials** | Cleanup: `https://www.googleapis.com/auth/spreadsheets.readonly` + `https://www.googleapis.com/auth/calendar.readonly`; operational: `https://www.googleapis.com/auth/spreadsheets` + `https://www.googleapis.com/auth/calendar.events` | Separates no-mutation probes from writes | Strong separation of duties and reduced blast radius for cleanup | Current loaders/service constructors are not separated by role; safe selection requires code/config changes outside this task and introduces dual-token selection risk. **Not safely selectable now.** |
| **D — current broad helper** | `https://www.googleapis.com/auth/gmail.readonly`, `https://www.googleapis.com/auth/gmail.send`, `https://www.googleapis.com/auth/gmail.modify`, `https://www.googleapis.com/auth/calendar`, `https://www.googleapis.com/auth/drive`, `https://www.googleapis.com/auth/contacts.readonly`, `https://www.googleapis.com/auth/spreadsheets`, `https://www.googleapis.com/auth/documents` | More access than the inspected code requires | No implementation change needed to retain current behavior | Violates least privilege and increases blast radius, review burden, token-theft impact, and evidence-leakage risk. **Reject.** |

### Why Option B wins

1. **Code fit:** current code writes all seven governed-record areas through Sheets and inserts Calendar events; Option A cannot perform those operations.
2. **Least privilege:** Option B removes all unrelated Gmail, Drive, Contacts, and Docs grants, and uses the narrower Calendar event scope rather than the broad Calendar scope. It does not claim delete/admin/sharing capability.
3. **Maintenance:** one operational credential avoids C’s dual-token routing, stale-token ambiguity, and backup/rollback complexity.
4. **Approval gates remain meaningful:** Sheets operations remain application-controlled; Calendar promotion still requires an existing draft, approval/status checks, idempotency, and the one-shot local authorization boundary.
5. **Current state is not silently changed:** because the source hardcodes D, selecting B requires a separately approved code/configuration change and verification package.

## 5. Candidate credential lifecycle (proposal only)

This lifecycle is a future controlled procedure. None of these actions occurred in CLEANUP-006B.

1. **Preserve the existing expired token untouched.** Do not inspect, refresh, rewrite, rename, delete, or replace it during candidate preparation. Treat its state as historical supplied state until an authorized operator handles it.
2. **Propose a separate candidate path** outside the current token path, with restricted permissions and a documented owner. Do not create the path or candidate token as part of this packet.
3. **Authorize only the selected Option B scope set** through an independently approved process. This packet contains no authorization URL and does not grant authorization.
4. **Evaluate only redacted derived metadata** with `scripts/google_oauth_candidate_acceptance.py`. The evaluator is pure and metadata-only (`scripts/google_oauth_candidate_acceptance.py:1-5`, `:42-64`, `:92-114`); it never reads or renders credential material. Use only its redacted invariant outcomes: `CREDENTIAL_NOT_VALID`, `CREDENTIAL_EXPIRED`, `GRANTED_SCOPE_SET_MISMATCH`, `CLIENT_IDENTITY_MISMATCH`, `REFRESH_TOKEN_MISSING`, `SERIALIZED_JSON_INVALID`, `SERIALIZED_SHAPE_UNEXPECTED`, `TOKEN_TYPE_UNEXPECTED`, `CANDIDATE_ACL_MISMATCH`, `EXISTING_TOKEN_CHANGED`, or `ACCEPTED` (`scripts/google_oauth_candidate_acceptance.py:27-39`, `:111-114`). Never record secrets, raw tokens, auth codes, or serialized credential content in evidence.
5. **Run bounded read-only probes before any promotion.** Use a fakeable/read-only probe plan: read the canonical full range for each governed Sheet tab; list the canonical Calendar resource with a bounded page/result limit; record counts and schema/identity checks; do not append/update/insert. Capture before and after fingerprints/counts sufficient to prove no mutation, without exposing resource IDs or row contents.
6. **Require explicit no-mutation proof.** Before/after evidence must show no Sheets row/header changes, no Calendar insertion, no Calendar update/delete, no public-site write, and no token-path modification. A dry-run must report `filesystem_writes: 0` (`scripts/sync_approved_safe_data.py:321-335`). `/daily` must use `persist_refresh=False` and an in-memory safe snapshot (`scripts/telegram_intake_router.py:2337-2347`).
7. **Promote separately and explicitly.** Acceptance of metadata and read-only probes is not promotion. A separate approval must name the candidate, selected scope set, intended consumer, and exact replacement window.
8. **Replace atomically with backup and rollback.** The future operator must create a restricted backup of the prior token, write the candidate to a temporary file in the same protected directory, validate it, atomically replace the selected operational path, verify permissions, and retain a tested rollback path. Do not leave a partially written credential visible to the gateway.
9. **Handle refresh deliberately.** Because the current loaders silently refresh and persist (`non_profit_hermes_ops.py:124-129`; `sync_approved_safe_data.py:110-117`), promotion must decide which process owns refresh persistence, verify the gateway’s selected path, and detect stale in-memory credentials. This is a future implementation/operations requirement.
10. **Close with evidence and hold release.** Redact acceptance codes and probe results; do not publish credential evidence. CLEANUP-007B remains held until its own authorization and release criteria are met.

## 6. Ready-to-send authorization block (not authorization)

The following text is a prepared request for an authorized human operator. It is **not itself authorization**, does not contain an OAuth URL, and must not be executed merely because it appears in this packet.

> **Authorization request — Google credential change for Non-Profit Hermes**
>
> Please authorize creation of one minimum operational credential for the Non-Profit Hermes integration with exactly these scopes:
>
> - `https://www.googleapis.com/auth/spreadsheets`
> - `https://www.googleapis.com/auth/calendar.events`
>
> Purpose: support the existing operational Sheets record/audit writes and the existing Calendar list/read plus explicitly approved event-insert path. No Gmail, Drive, Contacts, Docs, Calendar ACL, calendar sharing, calendar administration, or Calendar delete/update capability is requested or required by the inspected code.
>
> Before promotion, require: redacted candidate acceptance with invariant code `ACCEPTED`; exact client identity and scope-set match; refresh-token presence; candidate ACL match; proof that the existing token is unchanged; bounded read-only Sheets/Calendar probes with before/after no-mutation evidence; restricted permissions; an atomic replacement with backup; and a tested rollback. Keep the existing token untouched until explicit promotion approval. This request does not authorize a live OAuth flow, credential replacement, gateway restart, plugin deployment, publication, or CLEANUP-007B release.

## 7. Risk register

Likelihood and impact are qualitative planning judgments based on the inspected code and the proposed lifecycle. **Uncertainty** identifies what cannot be established without an authorized live check.

| Risk | Likelihood | Impact | Mitigation / gate | Uncertainty |
|---|---|---|---|---|
| Write-capable Sheets credential changes private records or headers | Medium | High | Prefer Option B over D; restrict operator access; require explicit operation approval, AuditLog review, backups, and bounded probes that never call append/update | Live account permissions and operator practice not inspected |
| Calendar misuse or unintended event insertion | Medium | High | Keep draft-first flow; require `ApprovalStatus=approved`, `Status=ready`, valid times, one-shot local authorization, and idempotency; retain live plugin default disabled | Live plugin deployment state not revalidated here |
| Overgrant from current broad helper | Certain in current source | High | Reject D; make any future scope change explicit and exact; verify granted scope set with redacted acceptance metadata | Existing grant was not accessed |
| Missing refresh token | Unknown | High | Reject candidate with `REFRESH_TOKEN_MISSING`; do not promote; preserve existing path | Historical supplied state only |
| Token theft or unauthorized local read | Medium | Critical | Restricted permissions, least privilege, no secrets in evidence, protected backups, atomic replacement, operator access review | Actual filesystem ACLs not inspected |
| ACL mismatch on candidate or backup | Unknown | High | Require `CANDIDATE_ACL_MISMATCH` rejection; verify owner/restricted mode before promotion | No credential or ACL command was run |
| Overwrite or accidental duplicate Sheets rows | Medium | High | Existing ID checks and audit writes; preserve backup; use dry-run and before/after evidence; review idempotency | Live data and concurrent writers not inspected |
| Silent refresh changes token while expected to be untouched | Medium | High | Treat current refresh persistence as a design risk; use `persist_refresh=False` for read-only cleanup/daily; define refresh owner before promotion | Runtime process state not inspected |
| Dual-token selection chooses wrong credential (Option C) | Medium | High | Do not select C without explicit role-based loader/config change and tests; record selected path and consumer | No dual-token implementation exists in current source |
| Gateway retains stale credentials after promotion | Medium | High | Explicitly verify selected path and reload/restart only under separate authorization; never assume replacement is live | Gateway was not restarted or inspected |
| Partial promotion leaves invalid/half-written credential | Low with controls / high without | Critical | Same-directory temporary write, validation, atomic replace, protected backup, rollback rehearsal | No promotion occurred; filesystem behavior not tested |
| Rollback failure | Low | Critical | Keep known-good backup untouched, verify backup readability/ACL, document one-step rollback, and test before release | No backup was created |
| Evidence leakage exposes identifiers or private rows | Medium | High | Redact workbook/calendar identifiers; record only counts, hashes/fingerprints approved for evidence, and acceptance codes; never include raw credential content | Live evidence set does not exist |
| Incorrect inference of Calendar delete/update/admin rights | Low | High | Document only observed list/insert and Sheet-side updates; do not infer capabilities from scopes; no ACL/sharing code path is required | Google-side granted role not inspected |
| Public preview publishes an unapproved record | Low to Medium | High | Preserve deny-by-default privacy/status/consent gates and explicit non-dry-run publication boundary; inspect generated output separately under its own gate | No live publication was run |

## 8. Acceptance checklist for a future authorized implementation

- [ ] Scope target is exactly Option B: Sheets plus Calendar events; no broad helper remains selected for the operational path.
- [ ] A separately approved code change replaces the hardcoded broad helper; this packet alone does not do so.
- [ ] Existing token is preserved untouched until promotion.
- [ ] Candidate path is separate, protected, and not confused with the current path.
- [ ] Candidate acceptance returns redacted `ACCEPTED`; no failed invariant is suppressed.
- [ ] Candidate client identity, exact scope set, refresh-token presence, serialized shape, token type, and ACL are verified without exposing values.
- [ ] Full-range read-only Sheets probes cover all seven governed tabs and AuditLog.
- [ ] Bounded Calendar list probe completes without insert/update/delete.
- [ ] Before/after proof shows no Sheet, Calendar, filesystem, public-site, or existing-token mutation.
- [ ] `/daily` remains read-only and uses non-persisting refresh behavior.
- [ ] Explicit promotion approval is recorded separately from candidate acceptance.
- [ ] Atomic replacement, restricted permissions, backup, and rollback are verified.
- [ ] Gateway/plugin/runtime verification is separately authorized; CLEANUP-007B remains held until its own release decision.

## 9. Exact file scope and limitations

**Authorized write scope:** exactly one file, `CLEANUP_006B_GOOGLE_CREDENTIAL_DECISION_PACKET.md`, in the specified worktree. No other repository file is authorized for modification.

**Static-source limitation:** this packet is based on the supplied handoff and static inspection of the cited source at the accepted offline revisions. No network, Google endpoint, OAuth flow, credential path, token file, gateway, plugin deployment, publication, or live account state was accessed. Claims about existing token status, live ACLs, live granted scopes, deployment state, and live data are not freshly verified here.
