# Security and Privacy — Non-Profit Hermes MVP

**Last updated:** 2026-07-12 (EVENT-004 post-capture documentation reconciliation; see `EVENT_004_LIVE_CALENDAR_PROMOTION_REPORT.md`)

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

Calendar creation is exception-only, not a general consequence of `/event`. The authoritative final EVENT-004 evidence JSON supports one renewed-explicitly-authorized promotion of the synthetic `private-review` draft `EVT-A31A0CF8`: one confirmed Calendar event (`cpq3e1oivn4ajb4t8ktemjuj0g`) with empty location and attendees, `PublicCalendarAllowed=no`, approved-calendar exclusion (`approved_calendar_count=0`), and authorization absent after success.

Future Calendar creation requires separate per-event human authorization, a scoped promotion guard, preflight, authorization consumption immediately before the first external attempt (non-reusable after a failed attempt), same-row Calendar ID persistence, and idempotent-retry verification. The EVENT-004 result does not authorize public-calendar inclusion, another promotion, plugin/gateway activation, Telegram registration, or public publication.

The direct installed-plugin daily invocation used for controlled verification was observed during the execution session to pass with an in-memory marker and zero writes, but it was not a human-originated Telegram-delivered message. The controlled local `/daily` CLI zero-write observation was likewise an execution-session observation. Neither observation is contained in the authoritative final evidence JSON, and neither proves Telegram transport or human delivery. Offline tests independently cover idempotence. See `EVENT_004_LIVE_CALENDAR_PROMOTION_REPORT.md` for the evidence boundary and audit IDs.

## Remaining concerns

- CLEANUP-003 is complete and keeps `/daily` in read-only in-memory state; it does not generate a public snapshot. Publication remains frozen, and no automatic approval backfill is authorized.
- The current OAuth token requests broader scopes than necessary (Gmail, Drive, Contacts, Documents, Sheets, Calendar). Least-privilege scope reduction remains a separate CLEANUP-005 concern.
- `google_token.json`, `.env`, and credentials must never be committed. Machine-specific paths remain a configuration concern for CLEANUP-005.

## Test safety

The project’s fake-based test suite does not make network calls. Explicit live-write operational modes remain separate from offline tests and require deliberate operator use. The one EVENT-004 live create was narrowly authorized, recorded, and is not a reusable authorization.
