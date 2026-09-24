---
name: non-profit-hermes
description: Use when operating the seven-command Non-Profit Hermes workflow. Keeps intake draft-first, privacy-classified, approval-gated, and auditable.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [nonprofit, telegram, privacy, approvals, audit]
    related_skills: []
---

# Non-Profit Hermes Operations

## Overview

Use the nonprofit commands and /board as a small, predictable operations interface. Keep intake draft-first, collect only necessary facts, preserve the private/public boundary, and verify each result before reporting success.

The workflow does not infer authorization from configuration or availability. A working integration permits an action only after the action's own privacy and approval conditions are satisfied.

## When to Use

Use this skill for:

- board-safe daily summaries;
- nonprofit request, donation, report, task, and inventory intake;
- unified event drafts, optional staffing and completion reporting;
- approval-controlled public-safe drafts.

Do not use it for automatic publication, broad Calendar authorization, payment processing, or exposing sensitive case details.

## Privacy Gate

Classify each fact before using it:

- `private` for identifying, contact, exact-location, personal, or otherwise sensitive information;
- `internal` for staff operations that must not be public;
- `board-visible` for reviewed board material;
- `public-safe` for minimized, non-identifying material eligible for an approval-gated public draft.

When uncertain, choose the more restrictive class. Do not invent missing information. Mark it `unknown` or ask one focused follow-up question.

## Command Workflow

### `/daily`

1. Read only approved-safe source data.
2. Summarize urgent items, dated commitments, resource gaps, pending approvals, and due follow-ups.
3. Keep private details out of the response.
4. Confirm the path performed no Google write, public-file generation, publication, or durable credential refresh.

Completion criterion: the summary is board-safe and the operation is verified read-only.

### `/need`

1. Capture the need, urgency, needed-by date, safe contact route, privacy level, and next action when provided.
2. Create or update a draft; do not infer a sensitive location or missing consent.
3. Ask only for facts required to move the draft forward.
4. Verify the resulting record and audit entry.

Completion criterion: the draft exists with unknowns and privacy state explicit.

### `/donation`

1. Capture the offered item, quantity, handoff method, availability, privacy state, and next action.
2. Keep public listing and public thanks as separate consent decisions.
3. Leave incomplete intake in draft or needs-review state.
4. Verify the resulting record and audit entry.

Completion criterion: the donation draft is traceable and no public consent was assumed.

### `/report`

1. Capture a concise activity summary, date, operational counts, follow-up needs, privacy level, and next action.
2. Keep sensitive notes out of any public summary.
3. Populate public-safe summary material only when policy and approval state permit it.
4. Verify the resulting record and audit entry.

Completion criterion: the report is classified, auditable, and safe for its stated audience.

### `/task`

1. Capture a clear title, owner if known, due date if known, priority, privacy level, and next action.
2. Keep tasks internal.
3. Do not turn a vague date into a Calendar event.
4. Verify the resulting record and audit entry.

Completion criterion: the task is actionable or its missing fields are explicitly listed.

### `/inventory`

1. Capture item, quantity, unit, category, threshold if known, condition, and next action.
2. Use the stable item identifier when updating an existing record.
3. Keep storage details private or internal.
4. Verify the resulting record and audit entry.

Completion criterion: the inventory record reflects the intended item and quantity without public exposure.

### `/event`

All new events use the unified Board model described below. Create drafts; publish only with explicit user authorization and the release gate satisfied. Calendar is a projection of published Board events. Historical Google-only drafts remain preserved, not the creation path for new events.

## Publication Boundary

Public-safe classification is not publication approval. Before any public action:

1. minimize the content to non-identifying facts;
2. tie the draft to approved-safe source records;
3. request approval for the exact text and destination;
4. publish only after that approval;
5. verify the exact released artifact and audit trail.

If wording changes after approval, return it to review.

## Common Pitfalls

1. Treating command availability as permission. Availability proves only that a handler exists; action-specific authorization is still required.
2. Treating `public-safe` as `approved`. It means eligible for review, not cleared for release.
3. Creating Calendar events from vague dates. Keep them as tasks or drafts until date, time, and exact authorization are present.
4. Reporting a mutation from a successful function return alone. Read back the intended record and confirm its audit evidence.
5. Reusing sensitive details in summaries. Minimize again at every audience boundary.

## Completion Checks

Before replying that work succeeded, confirm:

- [ ] the correct command and target record were used;
- [ ] missing facts remain unknown or were requested;
- [ ] privacy classification matches the content;
- [ ] every mutation has audit evidence;
- [ ] `/daily` remained read-only;
- [ ] Calendar projection reflects an authorized Board publication;
- [ ] publication had approval for the exact content;
- [ ] the final response separates completed, failed, and pending work.




# Unified nonprofit operator workflow

Telegram menu: /daily /need /donation /report /task /inventory /event /board /new /usage /status /model /stop.

Use scripts/nonprofit_workflow.py COMMAND ARGS for the same bounded operations as Telegram. Existing need/donation/report/task/inventory handlers remain authoritative for their Google records. Bare commands show safe help, never create records. For ordinary-language requests, extract the existing handler fields, ask for required missing details, and call the same dispatcher; never create a parallel storage path. A cash donation missing monetary fields in the current schema must be clarified, not converted into invented item quantities.

All new events are Board events; historical Google-only drafts remain history and must not be promoted as new events. /event manages definition, recurrence, capacity, staffing/completion settings and status. /board is read-first: staffing, open places including reserved offers, standby, cancellations and pending offers. Never edit SQLite or duplicate volunteers in Sheets. Board is the only source of signup/consent/SMS state.

Create/update via scripts/volunteer_board_operator.py --request, passing JSON through stdin rather than interpolating shell arguments. Shape: {"action":"create","authorized":true,"payload":{"event":{...}}}. Authorized may be true only for an actual user-requested write. Event fields: slug,name,description,location,startsAt,endsAt,capacity,status,timezone,staffingEnabled,standbyEnabled,completionReportRequired,completionStatement,seriesId,recurrenceRule,occurrenceDate. New events stay draft; staffing defaults off. Use timezone-aware conversion; default America/Denver. completionReportRequired requires staffing and an organizer-approved completionStatement. Do not invent a statement from an SMS body.

For update, payload has eventId,event and scope="one" for one explicit occurrence. For ambiguous recurring edits ask one vs future. Future edits use action series_update with payload.seriesId and occurrenceChanges:[{id,patch}], computing each changed occurrence's timestamps in its timezone across DST and updating recurrenceRule as appropriate. action series_prepare with seriesId materializes the next horizon from the Board-stored rule. Weekly rule: {"frequency":"weekly","weekday":5,"startTime":"15:45","endTime":"17:00","timezone":"America/Denver","horizon":12}. Never overwrite a individually changed or cancelled occurrence during replenishment.

Saturday Pantry: series saturday-pantry, Saturdays15:45–17:00 Denver, 302 South Ave Grand Junction CO, six places, standby enabled, completion reporting disabled. Preserve the twelve drafts; no automatic publication/invitations.

DONE is deterministic: an eligible confirmed volunteer completes the whole report-required event, not a per-person attendance record. Ambiguous DONE needs an explicit keyword. First completion records expected statement/time/volunteer and closes pending offers; repeats must not complete another task. No arbitrary SMS body storage or incident-reporting workflow.

Organizer drop/send remain explicit authorized bounded operations through Board API and existing real_use_review_complete release gate. Explain that a drop may send a standby offer. Do not retry sends after a timeout: the existing admin send endpoint has no request idempotency key. Never expose admin/Twilio credentials, phone numbers or raw SMS in responses or logs. Volunteer IDs and display names are permitted for authorized organization staffing views.

Google credentials use C:\Users\fallo\AppData\Local\hermes\google_token.json; profile locations resolve to it. No new OAuth needed. Google Workspace Docs/Drive implementations exist; real Docs usage is allowed when requested, but no dummy Docs. Private workbook remains private.

Member Operations is a one-way sanitized view of both Board and existing Google operations. scripts/member_operations_projection.py owns projections; inspect its inspection_status() for the workbook URL, last success and pending state. Never synchronize member-sheet edits back to source. Names use Board display name or Volunteer #ID; no phones, consent/STOP, Twilio IDs, private notes or message bodies. Unclassified task/donation details remain withheld; counts are visible. Do not mark those records shareable without user review.

Report source failures/stale Google projections honestly. State may be saved in Board while Google is pending; never say a write failed merely because its projection is delayed. User publication authorization and the real-use wording gate are separate from technical integration success.

## Easy organizer changes

Accept ordinary requests such as “Move this Saturday to 4 PM”, “Make future Saturdays 8 places”, or “Require DONE for the sock pickup”. Resolve the current Board record, ask only for missing scope/date/required completion statement, and use the existing bounded API. Never ask the user to write JSON or find database IDs. After a change, reply with event/date and the before → after value, plus whether Google is current or pending. Publication is separate from changing an event. Do not promise live SMS delivery from configuration or health checks alone.
