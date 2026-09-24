## Authoritative Volunteer Board and Google operator connection

For volunteer events, Saturday Pantry, signups, standby, cancellations, consent and SMS, use the Volunteer Board API connector below. Do not use legacy Sheets Volunteers or Calendar event drafts as a second source of volunteer truth. Existing unrelated nonprofit Sheets/Calendar workflows remain separate.

Natural-language requests such as "show Pantry places" or "check the volunteer board" should execute the connector immediately for reads and return concise human summaries. Keep the Telegram menu: /board /new /usage /status /model /stop. /board status and /board signups 1 work without adding menu entries.

Connector: C:\Users\fallo\non-profit-hermes-mvp\scripts\volunteer_board_operator.py
Dedicated Python: C:\Users\fallo\AppData\Local\hermes\staging\non-profit-hermes-v1\20260804T170601Z\telegram-canary-remediation-20260805T100000Z\venv-telegram-fresh\Scripts\python.exe

Read commands: list, show 1, status, signups 1. For structured operations run the connector with --request and supply a JSON object via stdin, not shell-interpolated arguments. Shape: {"action":"signups","payload":{"eventId":1}}. Supported actions: status, list, show, signups, create, update, send, drop. Never read its credential JSON into the conversation.

Create: payload.event contains API fields slug,name,description,location,startsAt,endsAt,capacity,status; create drafts only. Update: payload.eventId and payload.event with intended changed fields. Timestamps use UTC ISO8601; convert Denver dates including DST. Preserve the twelve Pantry drafts, Saturday 15:45-17:00 Denver, six places, unless the user explicitly requests a change.

For any write, authorized:true is permitted only when the user actually authorized that exact action. For send, obtain exact recipient volunteerId, message body and optional eventId approval; payload uses those fields. For drop, obtain exact signupId authorization and explain that cancellation may send an offer to standby. Never infer sending authorization from a request to reconnect, inspect, list or test. Both use existing Board API functions, including consent checks and deterministic standby. Do not retry sends automatically: the current admin send endpoint has no client idempotency key. A timeout needs delivery reconciliation, not resending.

Publication, send and drop remain held until the existing local real_use_review_complete gate is satisfied. Do not flip that gate automatically. No invitations, publication or actual SMS occurred during reconnection. Do not access SQLite, duplicate volunteer records, expose roster names/phones, log bodies or load Twilio credentials. Signups return only IDs, states and counts. The API has no delivery-history list endpoint; do not invent a delivered status or bypass it with direct DB reads.

Google: fresh local authorization completed 2026-09-24 with the existing OAuth client. Canonical credential: C:\Users\fallo\AppData\Local\hermes\google_token.json. Profile google_token.json and private/google/google_token.json are symbolic links to this same protected token. The actual profile Workspace helper loaded it successfully; authenticated Drive, configured Sheets and configured Calendar reads passed. Docs scope is granted and existing Docs code is present, but no accessible Google Doc was found for a harmless read. Request an existing document link before claiming Docs read verification; do not create test documents. No new OAuth flow is needed.
