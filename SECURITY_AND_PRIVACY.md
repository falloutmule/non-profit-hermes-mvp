# Security and Privacy — Non-Profit Hermes MVP

**Last updated:** 2026-07-11 (CLEANUP-001)

## Privacy model

Privacy is a **hard gate**, not a formatting preference. The system serves vulnerable populations. Any leak of identifying information could cause real harm.

### Never publish

The following must never appear on GitHub Pages, in `docs/`, or in any board-visible public surface unless a human has explicitly approved the exact text and it is safe:

- exact shelter/camp/housing locations
- full names of people receiving help
- phone numbers
- addresses
- medical details
- addiction details
- legal details
- family crisis details
- immigration details
- police-related details
- interpersonal conflict details
- identifying photos

### SensitiveNotes handling

If a message contains private details that should be retained but not published:

- store them in the SensitiveNotes logical area
- mark the sensitivity type
- keep access level private
- do not reuse those details in public drafts

The `SensitiveDetails` field in the Reports schema **must remain empty** in all automated writes. Never auto-populate sensitive data.

## Publication gates

Every record type has an explicit privacy filter in `scripts/sync_approved_safe_data.py`:

### Requests

**Current behavior:** Exported when `PrivacyLevel` is in `{board-visible, public-safe, board-visible-test}`.

**Known gap (P0):** The sync script does not yet check `ConsentToShare` or `Status`. Draft and needs-info requests may be exported. Target gate (CLEANUP-002):

- `PrivacyLevel` is `public`
- `ConsentToShare` is affirmative
- `Status` is in `{new, ready, open, in-progress}`
- Exclude: `draft`, `needs-info`, `private-review`, `private-hold`, `cancelled`, `rejected`

### Reports

Exported only when:
- `PrivacyLevel` is not `private-review` or `private-hold`
- `Status` is not `draft` or `needs-info`
- `public_summary_allowed` is not `no`

### Donations

Exported with safe fields only:
- DonorName stripped or generalized
- DonorContact never exported
- LocationPrivate never exported
- PickupOrDropoff not exported

**Known gap (P0):** Donations currently lack an explicit `PublicListingAllowed` field. All donation rows are exported regardless of review status. This is scheduled for cleanup.

### Calendar

Two-source join required:
1. **CalendarLog** must have: non-empty `CalendarEventID`, `PrivacyLevel` in approved set, `PublicCalendarAllowed=yes`, `ApprovalStatus=approved`, `Status=confirmed/ready`, non-empty `PublicTitle`.
2. **Google Calendar** must confirm the event ID still exists and is not cancelled.

Raw Google Calendar event title, description, location, and attendees are **never** exported. Only the public-safe fields from CalendarLog are used.

### Board log

Currently exports raw AuditLog entries including internal IDs. **This is a known P0 issue.** The target state is aggregate summaries only (e.g., "3 needs updated, 2 donations created").

### Tasks and Inventory

Tasks and inventory are **internal only**. They must never appear in `docs/` or approved-safe JSON.

## Calendar creation policy

**Calendar creation is disabled** in the live `/event` plugin (`allow_calendar_creation=False`).

- EVENT-001 through EVENT-003 built the privacy gate, draft backend, and router/plugin.
- EVENT-003 verified live draft-only flow (no Calendar write).
- EVENT-004 (unstarted) will authorize the first live Calendar promotion.

No live Google Calendar event has been created by any `/event` flow.

## OAuth scopes

The current OAuth token requests broader scopes than needed:

```
Gmail, Drive, Contacts, Documents, Sheets, Calendar
```

**Target (CLEANUP-005):** Reduce to least privilege:

```
spreadsheets (Sheets)
calendar (Calendar)
```

Scope reduction requires controlled re-authorization with rollback instructions.

## Token and credential safety

- `google_token.json` must never be committed.
- `.gitignore` must include `google_token.json`, `.env`, and credential patterns.
- Machine-specific paths (`C:\Users\fallo\...`) should be externalized to config/env vars (CLEANUP-005).

## Test safety

**Current test modes write live data.** The router `--test` flag and backend `--test-write` flag call real Google services and create real rows in the production Sheet.

**Target (CLEANUP-005):**
- Default test mode uses in-memory fakes only.
- Live-write test modes require explicit flags AND an environment variable.
- CI never loads real tokens, accesses Google, or mutates `docs/`.

## Known privacy gaps (P0 cleanup)

These are documented in the cleanup handoff and scheduled for CLEANUP-002:

1. Schema divergence may cause draft filtering to fail silently.
2. `public_summary_allowed` is not persisted in the Reports schema.
3. Donations have no explicit publication-consent field.
4. Board log exposes internal Task/Inventory/Event IDs and audit IDs.
5. Public HTML does not escape user-controlled Sheet values (XSS risk).
6. Sheet reads stop at row 100, which can hide records from export filtering.

Until these are resolved, treat the public site as potentially incomplete and do not publish a new snapshot.
