# Member Operations projection

One-way projection from Volunteer Board and the existing private Google operations workbook. No SMS endpoints or Board event writes are available to this worker.

## Runtime

Use the existing dedicated nonprofit Python interpreter and canonical Google OAuth setup. Private state: `%LOCALAPPDATA%\hermes\profiles\nonprofit-v1\private\configuration\member-operations.json`. The parent directory must retain its existing restricted ACL. State stores only workbook identity, initialization, timestamps, retry counters, and checkpoints; never roster copies or credentials. The adjacent `volunteer-board.json` supplies the loopback admin credential.

Initialize once:

```powershell
& $NonprofitPython C:\Users\fallo\non-profit-hermes-mvp\scripts\member_operations_projection.py --initialize
```

Initialization discovers an existing uniquely tagged workbook before creating one, refuses non-owner sharing, adds protected generated tabs, and persists the resource identity. No sharing permissions are added. If initialization is interrupted, rerun it; never delete the config to make another workbook.

Run every minute using the existing nonprofit service account identity in a separate no-login Scheduled Task, IgnoreNew, five-minute execution limit, StartWhenAvailable:

```powershell
& $NonprofitPython C:\Users\fallo\non-profit-hermes-mvp\scripts\member_operations_projection.py --once
```

`--force` bypasses idle/backoff for a deliberate reconciliation. The process uses a kernel lock released even on crash. Retrying outbox delivery is safe: views replace keyed source snapshots atomically in Sheets, Calendar IDs are deterministic, and Board acknowledgements follow all Google success. Google failure leaves Board outbox pending. Five-minute reconciliation repairs Google-authoritative direct edits and projection drift. Exponential retry delay caps at one hour. No exception payloads are logged.

`inspection_status()` returns only the member URL, last successful sync, and status for `/daily`. Stale timestamps remain visible; failures appear in local config as sync pending. Reconciliation reads private operational records without copying raw records to disk.

## Privacy and source mapping

Events/Staffing/Activity come from the narrow Board projection API. Private descriptions are not exported. Requests and donations require explicit board-visible/public-safe/member-visible classification. Reports require that classification and a nonempty PublicSummaryDraft. Public outreach consent flags do not grant or deny internal member inspection. Inventory exposes only the user-approved item/quantity/unit/minimum/status fields unless marked private; notes and locations remain excluded. Tasks require explicit safe classification: the current source has no PrivacyLevel column, so existing unclassified task text is withheld unless the user explicitly approves IDs in private configuration `approved_record_ids: {"Tasks": ["TASK-ID"]}`; explicitly private records remain excluded even if allowlisted. Source counts/status aggregates remain visible in Overview for all categories. This is a privacy gap to resolve, not a claim that no tasks exist. Donations lack monetary amount columns; no amount is guessed from description text.

Existing CalendarLog mappings with EventDraftID `board:<id>` are honored. Otherwise deterministic Google Calendar IDs encode the stable Board ID; no duplicate CalendarLog ledger is created. Drafts never create Calendar events. Cancellation updates only an existing mapped event; completion retains history. No guests are added and sendUpdates is none.

The generated workbook is an inspection view. Sheet protection prevents accidental edits and is not a privacy boundary. User sharing is deliberate and separate. Never add private contacts, raw audit Before/After, notes, phone numbers, tokens, or SMS bodies. Never synchronize workbook edits back to Board.
