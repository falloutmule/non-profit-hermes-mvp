# Live Need Sloppy Intake Fix Report

**Date**: 2026-07-07  
**Status**: updated; live `/need` follow-up tracking fixed and verified

## Goal
Make `/need` follow-up handling attach the next plain message in the same Telegram chat/session to the exact active draft automatically, unless the user explicitly names another `RequestID`.

## What Was Done

1. **Added per-chat active draft tracking**
   - Implemented local active-draft state at:
     - `C:\Users\fallo\AppData\Local\hermes\state\telegram_active_need_drafts.json`
   - `/need` now stores `active_need_request_id` for the chat/session scope when it creates a `needs-info` draft.
   - When the draft becomes `ready`, the active pointer is cleared.

3. **Changed follow-up routing**
   - Plain text follow-up messages are checked against the active draft first.
   - If the follow-up names another `RequestID`, that explicit target wins.
   - If multiple open drafts exist and no active pointer resolves the target, the router asks which `RequestID` to use.
   - The router no longer searches old sessions before checking the active draft.

4. **Added a conversation-style test**
   - Added a test sequence in `scripts/telegram_intake_router.py`:
     - `/need 6 rolls of toilet paper`
     - `urgency=normal needed_by=unknown location="public-safe test area" privacy_level=board-visible status=ready`
   - The test passed locally and confirmed the follow-up attached to the newly created draft without repeating the `RequestID`.

5. **Verified with live Telegram source routing**

   - Created `REQ-LIVE-20260707-005` via `/need 6 rolls of toilet paper`.
   - Sent the follow-up line without a `RequestID`.
   - The follow-up attached to the active draft automatically and updated the same row.

5. **Synced approved-safe docs**
   - Ran `python scripts/sync_approved_safe_data.py` after the live update.
   - Regenerated approved-safe JSON and current-needs pages.

## What Was Verified in Live Telegram

### Draft creation
The live `/need` call created:

- `REQ-LIVE-20260707-005`
- Initial status: `needs-info`
- Active pointer stored for the live chat/session scope

### Follow-up attach
The plain follow-up message:

- `urgency=normal needed_by=unknown location="public-safe test area" privacy_level=board-visible status=ready`

was attached to `REQ-LIVE-20260707-005` automatically, with no `RequestID` repeated.

### Final row state
Verified row fields for `REQ-LIVE-20260707-005`:

- `NeedDescription`: `6 rolls of toilet paper`
- `Urgency`: `normal`
- `NeededBy`: `unknown`
- `LocationPublicSafe`: `public-safe test area`
- `PrivacyLevel`: `board-visible`
- `Status`: `ready`
- `NextAction`: `review`

### Active pointer cleanup
Verified the active-draft state file is now empty after the request reached `ready`.

### Docs / daily
Verified after sync:

- `docs/current-needs.html` includes `REQ-LIVE-20260707-005`
- `docs/current-needs/index.html` includes `REQ-LIVE-20260707-005`
- `docs/data/approved_needs.json` includes `REQ-LIVE-20260707-005`
- `/daily` shows `REQ-LIVE-20260707-005` exactly once

## What Failed

- None blocking for this fix.

## Current Exact State

- `/need` now keeps a per-chat active draft pointer.
- Plain follow-up text uses that pointer first.
- Explicit `RequestID` still overrides the pointer.
- The active pointer clears when the request becomes `ready`.
- `REQ-LIVE-20260707-005` is board-visible and present in current-needs docs.

## Remaining Blockers

- None for the `/need` follow-up fix itself.

## Next Actionable Step

- If desired, apply the same per-chat active-target pattern to `/donation` follow-ups next.

## Evidence Paths

- `C:\Users\fallo\non-profit-hermes-mvp\scripts\telegram_intake_router.py`
- `C:\Users\fallo\non-profit-hermes-mvp\scripts\non_profit_hermes_ops.py`
- `C:\Users\fallo\non-profit-hermes-mvp\docs\data\approved_needs.json`
- `C:\Users\fallo\non-profit-hermes-mvp\docs\current-needs.html`
- `C:\Users\fallo\non-profit-hermes-mvp\docs\current-needs\index.html`
