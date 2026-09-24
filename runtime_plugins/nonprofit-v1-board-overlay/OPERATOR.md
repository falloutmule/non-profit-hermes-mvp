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
