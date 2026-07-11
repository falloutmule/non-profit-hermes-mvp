# EVENT-002 Durable Event-Draft Backend — Implementation & Verification Report

> **Amendment (2026-07-11, CLEANUP-001):** The historical builder text below was written pre-commit. Final status:
>
> - **Final implementation commit:** `40cdfb6f6a044b74d049114647dc5ae498c53903` (`feat: add durable approved event draft backend`)
> - **Independent checker:** PASS.
> - **Live Google Sheets create/update verification:** Completed (see §6 below).
> - **Live Google Calendar promotion:** NOT performed — explicitly out of scope for EVENT-002 and remains untested live.
> - **Current canonical status:** See [PROJECT_STATUS.md](PROJECT_STATUS.md).
>
> The original report text is preserved below as historical builder evidence.

**Event:** EVENT-002 — durable event-draft backend (CalendarLog-based drafts + approval-gated calendar promotion)
**Branch:** `main` @ `db953b33e1ded49f840413f6b487e59c2be9f469` (tree was clean before edits)
**Date:** 2026-07-10
**Author:** builder subagent (Hermes)
**Commit status:** NOT committed / NOT pushed (per task constraints).

---

## 1. Scope & constraints honored

- ✅ Edited ONLY `scripts/non_profit_hermes_ops.py`, `tests/test_event_draft_backend.py` (new), and this report.
- ✅ Did NOT touch `scripts/telegram_intake_router.py`, `scripts/sync_approved_safe_data.py`, any plugin, or `docs/`.
- ✅ Did NOT enable an event plugin, implement router `/event`, restart the gateway, or create/edit/delete a real Google Calendar event.
- ✅ No live Google calls were made at any point — Sheets and Calendar are in-memory fakes in the tests.
- ✅ `create_calendar_event_from_draft` is **fake-testable only**; no production call was executed against live Calendar.

## 2. What was implemented

### 2.1 `scripts/non_profit_hermes_ops.py`
- **Refactor (EVENT-001 preserved):** extracted `_insert_google_calendar_event(svc_cal, *, title, description, location, start, end)` as a shared Google Calendar insertion helper. `create_calendar_event` (EVENT-001) now calls it; behavior, idempotency-on-title, and the `ensure_header(CalendarLog)` guard before append are unchanged.
- **`upsert_event_draft(...)`** — keywords: `event_draft_id, event_title, event_type, start_time, end_time, description, location, private_location, attendees, related_task_id, related_request_id, related_donation_id, privacy_level, public_calendar_allowed, public_title, public_description, public_location, approval_status, status, source_link, notes`.
  - Generates `EVT-XXXXXXXX` when `event_draft_id` absent.
  - `ensure_header(CalendarLog)` before read/write.
  - Appends if `EventDraftID` absent; updates the same row if present; never creates a second row for the same id.
  - Preserves existing values when an update param is empty/omitted.
  - `CalendarEventID` stays blank during draft create/normal update.
  - New-draft defaults: `PrivacyLevel=private-review`, `PublicCalendarAllowed=no`, `ApprovalStatus=needs-info`, `Status=needs-info`, `CreatedBy=Hermes`.
  - Writes `LastUpdated` on every write; returns `'created'` / `'updated'`.
  - AuditLog create/update with `TargetItem CalendarLog/<EVT>`.
- **`update_event_draft(...)`** — strict update:
  - Returns `not_found` for unknown `EventDraftID`; no silent row creation.
  - Partial non-empty updates only; preserves `CalendarEventID`.
  - Writes before/after audit; returns `updated`.
- **`_as_timezone_aware(start_time, end_time)`** — accepts tz-aware `datetime` or ISO **with offset** (or `Z`). **Rejects naive** `datetime` / `'2026-07-12T09:00:00'` (no silent UTC guess) → `ValueError`. Stdlib only (no `iso8601` dependency).
- **`create_calendar_event_from_draft(svc_cal, svc_sheets, *, event_draft_id)`** — final approved promotion:
  - Blocks unless: draft exists, `CalendarEventID` blank, `EventTitle` nonempty, `StartDateTime` tz-aware/offset ISO, `EndDateTime` safe (or defaults +1h), `ApprovalStatus=approved`, `Status=ready`. Does **NOT** require `PublicCalendarAllowed=yes`.
  - On success: creates ONE calendar event via PRIVATE operational fields (`EventTitle`, `Description`, `Location`); title prefixed `'EVT-XXXXXXXX — <title>'`; never uses `PublicTitle` as operational title. Updates the SAME `CalendarLog` row with `CalendarEventID`, `ApprovalStatus=created`, `Status=confirmed`, `LastUpdated`. No second `CalendarLog` row; one AuditLog row (`action create-calendar-event`). Returns `{status:'created', id, calendar_id}`.
  - Idempotency: if `CalendarEventID` already populated, returns `already_created` with existing id, **no second insert**. Exactly one `CalendarLog` row, exactly one insert on retry.

### 2.2 `tests/test_event_draft_backend.py` (new)
Stateful in-memory fake `FakeSheetsStore` (24-column `CalendarLog`) + `FakeCalendarService` (counts inserts, captures body) + `RecordingSheets`/`RecordingCalendar` for call-order assertions. No network.

## 3. Verification tiers (per task)

| Tier | Meaning | Status |
|------|---------|--------|
| **LOCAL FAKE-VERIFIED** | Logic exercised against in-memory fakes (no network). | ✅ All Tests 1–8 pass |
| **LIVE GOOGLE SHEETS** | Real `CalendarLog`/`AuditLog` writes on the production Sheet. | ✅ Parent-controlled live Sheets verification done (see §6) |
| **LIVE GOOGLE CALENDAR** | Real `create_calendar_event_from_draft` insert against live Calendar. | ⛔ NOT TESTED AGAINST LIVE GOOGLE CALENDAR (explicitly out of scope for EVENT-002) |

### 3.1 Test results — LOCAL FAKE-VERIFIED (ran here)

```
python -m pytest tests/test_event_draft_backend.py tests/test_event_calendar_privacy.py -q
→ 21 passed, 11 subtests passed
```

| ID | Contract test | Result | Live ID placeholder |
|----|---------------|--------|---------------------|
| 1 | new draft → one row + correct defaults; `EVT-XXXXXXXX` generated | ✅ PASS | `TEST-DRAFT-001` |
| 1b | generated id regex `EVT-[0-9A-F]{8}` | ✅ PASS | `TEST-DRAFT-001` |
| 1c | defaults when optional fields omitted (`private-review`/`no`/`needs-info`/`Hermes`) | ✅ PASS | `TEST-DRAFT-001` |
| 2 | upsert existing → row count preserved + omitted values kept; `CalendarEventID` blank | ✅ PASS | `TEST-DRAFT-002` |
| 3 | strict unknown update → `not_found`, no row creation | ✅ PASS | — |
| 3b | strict update preserves existing `CalendarEventID` | ✅ PASS | `TEST-DRAFT-003` |
| 4 | approval-gate blocks: missing title / missing start / naive start / invalid end / `ApprovalStatus≠approved` / `Status≠ready` → no insert, `CalendarEventID` blank | ✅ PASS (6 subtests) | `TEST-DRAFT-BLOCK-*` |
| 5 | successful fake creation → exactly one insert, same row populated (`created`/`confirmed`) | ✅ PASS | `TEST-DRAFT-CREATE-001` |
| 6 | duplicate retry → `already_created`, no second insert, one row | ✅ PASS | `TEST-DRAFT-CREATE-001` |
| 7 | privacy fields stored separately; operational title uses private fields, never `PublicTitle` | ✅ PASS | `TEST-DRAFT-PRIV-001` |
| 7b | `private_location` set → calendar event has no `location` field | ✅ PASS | `TEST-DRAFT-PRIV-002` |
| 8 | `CalendarLog` schema unchanged (24 cols, exact order) | ✅ PASS | — |
| 8b | EVENT-001 `ensure_header` before append still holds after refactor | ✅ PASS | — |

### 3.2 Live verification placeholders (superseded by §6)

The placeholders below were the original stubs. Live Google **Sheets** tiers (`LIVE-EVENT-001`/`LIVE-EVENT-002`) are now populated with exact evidence in §6. Live Google **Calendar** tiers (`LIVE-EVENT-003/004/005`) were **NOT** performed — live Calendar promotion is explicitly out of scope for EVENT-002.

- `LIVE-EVENT-001` — Live `upsert_event_draft` (new draft) → **DONE**, see §6.
- `LIVE-EVENT-002` — Live `update_event_draft` partial update → **DONE**, see §6.
- `LIVE-EVENT-003` — Live `create_calendar_event_from_draft` (approved+ready) → **NOT TESTED AGAINST LIVE GOOGLE CALENDAR**.
- `LIVE-EVENT-004` — Live idempotency retry → **NOT TESTED AGAINST LIVE GOOGLE CALENDAR**.
- `LIVE-EVENT-005` — Live naive-start block → **NOT TESTED AGAINST LIVE GOOGLE CALENDAR**.

## 4. Build / test commands used (all local, no network)

```bash
python -m py_compile scripts/non_profit_hermes_ops.py tests/test_event_draft_backend.py
python -m pytest tests/test_event_draft_backend.py tests/test_event_calendar_privacy.py -q
git diff --check   # clean, no whitespace errors
```

## 5. Notes / caveats
- `create_calendar_event_from_draft` intentionally does NOT require `PublicCalendarAllowed=yes`; it promotes any `approved`+`ready` draft using private operational fields. Public-safe gating for the *published* calendar remains enforced downstream by `sync_approved_safe_data.py` (EVENT-001), unchanged.
- `_as_timezone_aware` uses `datetime.fromisoformat` (Python 3.11+), accepting offset and trailing `Z`; naive values raise `ValueError` and cause the function to block rather than guess UTC.
- This report does **NOT** claim checker approval. It records local fake-verified results only; live tiers remain pending parent-controlled testing.

## 6. Parent-controlled live Google Sheets verification

**Scope:** Live Google **Sheets** only (CalendarLog + AuditLog). Live Google **Calendar** promotion was NOT exercised (out of scope for EVENT-002).

### 6.1 LIVE-EVENT-001 — live `upsert_event_draft` (new draft)
Created one safe fake draft on the production Sheet:

| Field | Value |
|-------|-------|
| EventDraftID | `EVT-1718BB9F` |
| EventTitle | `Safe fake EVENT-002 backend draft` |
| EventType | `test` |
| Description | `TEST RECORD - no real event` |
| PrivacyLevel | `private-review` |
| PublicCalendarAllowed | `no` |
| ApprovalStatus | `needs-info` |
| Status | `needs-info` |
| SourceMessageLink | `hermes:event-002-backend-test` |
| Notes | `EVENT-002 TEST RECORD` |

- `CalendarLog` data-row count **before** update = **5**; **after** update = **5** (same row updated, no duplicate row).
- `CalendarEventID` remained **blank** throughout.

### 6.2 LIVE-EVENT-002 — live `update_event_draft` (partial update, same row)
Updated the same `EventDraftID` `EVT-1718BB9F`:

| Field | New value |
|-------|-----------|
| EventType | `backend-test` |
| Notes | `EVENT-002 TEST RECORD - update verified` |
| Status | `cancelled` |
| ApprovalStatus | `rejected` |

- Same row updated in place — data-row count unchanged (5 → 5, no duplicate).
- `CalendarEventID` remained **blank** throughout.

### 6.3 Live AuditLog evidence (TargetItem `CalendarLog/EVT-1718BB9F`)

| AuditID | action | result |
|---------|--------|--------|
| `AUDIT-EEA7D718` | create | success |
| `AUDIT-A29FCE01` | update | success |

- Live audit count for this draft = **2**.

### 6.4 Out-of-scope / not performed
- `create_calendar_event_from_draft` was **NOT** invoked against live Google Calendar.
- **No Google Calendar event was created.**
- Live tiers `LIVE-EVENT-003/004/005` are **NOT TESTED AGAINST LIVE GOOGLE CALENDAR**.

### 6.5 State of the test record
- The row was **intentionally NOT deleted** and remains a clearly marked safe fake test record on the Sheet.

### 6.6 Commit status
- Current HEAD placeholder: `db953b3`.
- Commit/push happens **after this report update only if the parent decides**. No commit/push performed by this update.
- This report does **NOT** claim checker approval.
