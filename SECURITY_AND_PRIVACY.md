# Security and Privacy — Non-Profit Hermes MVP

**Last updated:** 2026-07-11 13:48 MDT (CLEANUP-002 closeout)

## Privacy model

Privacy is a hard gate, not a formatting preference. Exact locations, full names, phone numbers, addresses, medical, addiction, legal, family-crisis, immigration, police, and interpersonal-conflict details, plus identifying photos, must not appear in GitHub Pages, `docs/`, or another public surface unless a human has approved the exact safe text.

`SensitiveDetails` in Reports remains empty for automated writes and is never exported. Reports export only the approved `PublicSummaryDraft`, never raw `Summary` or `SensitiveDetails`.

## Implemented deny-by-default publication gates

CLEANUP-002 implemented the following controls in approved-safe exports:

- Requests require approved privacy (`board-visible`, `public-safe`, or `board-visible-test`), an exact public status, and affirmative `ConsentToShare`.
- Donations require approved privacy, an exact public status, and affirmative `PublicListingAllowed`.
- Reports require approved privacy, an exact public status, affirmative `PublicSummaryAllowed`, and a non-empty `PublicSummaryDraft`.
- Affirmative values are limited to `yes`, `true`, `1`, and `approved` after normalization; blank and non-affirmative values deny export.
- Newest-record deduplication occurs before gates, so a newer private or `needs-info` duplicate suppresses an older public candidate.
- Tasks and Inventory remain internal-only and have no public export status.
- Public HTML escapes user-controlled values.
- Board-log output is aggregate-only and excludes internal Task, Inventory, Event, and audit IDs.

These controls resolve the former schema divergence, row-100 truncation, missing donation gate, report-consent persistence gap, HTML-escaping gap, board-log identifier exposure, and missing export deduplication.

## Calendar policy and EVENT-004 boundary

Calendar creation is disabled in the live `/event` plugin (`allow_calendar_creation=False`). EVENT-001 through EVENT-003 completed privacy-gated draft handling; EVENT-004 is **unstarted and blocked**. No live Google Calendar event has been created by the `/event` flow.

## Remaining concerns

- `/daily` remains coupled to generation behavior. Publication is frozen until CLEANUP-003 separates the daily summary from generation; no public snapshot update or automatic approval backfill is authorized.
- The current OAuth token requests broader scopes than necessary (Gmail, Drive, Contacts, Documents, Sheets, Calendar). Least-privilege scope reduction remains a separate CLEANUP-005 concern.
- `google_token.json`, `.env`, and credentials must never be committed. Machine-specific paths remain a configuration concern for CLEANUP-005.

## Test safety

The project’s fake-based test suite does not make network calls. Explicit live-write operational modes remain separate from offline tests and require deliberate operator use.
