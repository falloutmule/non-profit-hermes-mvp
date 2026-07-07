# Live Donation Command Report

**Date**: 2026-07-07  
**Status**: completed; live `/donation` draft intake wired and verified

## Goal
Allow Telegram `/donation` to create safe donation draft records through the existing router/backend, using the same cautious pattern as `/need`.

## What Was Done

1. **Wired live `/donation` intake**
   - Added live donation draft creation in `scripts/telegram_intake_router.py`.
   - `/donation` now accepts sloppy input like:
     - `/donation 3 coats and 2 blankets`
   - The router auto-generates `DonationID` when the user does not provide one.
   - Donation drafts default to `status=needs-info` and `privacy_level=private-review`.
   - Missing details no longer fail the command.

2. **Added active donation draft tracking**
   - Added `active_donation_id` storage in the same local Telegram draft state file used by the need flow.
   - Plain follow-up text now attaches to the active donation draft first.
   - Explicit `DonationID` overrides the active draft.
   - The active donation pointer clears when status becomes `ready`.

3. **Kept `/need` behavior intact**
   - The existing `/need` explicit flow and follow-up handling remain functional.
   - Plain follow-up routing now tries donation first, then need, so `/donation` follow-ups work without breaking the need path.

4. **Extended donation row support in backend helpers**
   - Added donation update support in `scripts/non_profit_hermes_ops.py`.
   - Donation rows now carry the fields needed for draft/follow-up updates:
     - `ReceiptNeeded`
     - `ThankYouNeeded`
     - `ConsentToPublicThanks`
     - `Notes`

5. **Kept approved-safe export private-safe**
   - `scripts/sync_approved_safe_data.py` already exports only safe donation fields.
   - Donor contact and private location fields are not exported to docs.

## What Was Verified in Live Telegram

### 1) Draft creation
Sent:

- `/donation 3 coats and 2 blankets`

Verified result:

- `DonationID`: `DON-47D11AAA`
- `ItemDescription`: `3 coats and 2 blankets`
- `Status`: `needs-info`
- `Privacy`: `private-review`
- Missing fields returned:
  - `pickup_or_dropoff`
  - `location`
  - `available_date`
  - `receipt_needed`
  - `consent_to_public_thanks`
  - `next_action`

### 2) Follow-up attach
Sent plain follow-up with no `DonationID`:

- `pickup_or_dropoff=dropoff location="public-safe test area" available_date=unknown receipt_needed=no consent_to_public_thanks=no status=ready next_action=review`

Verified result:

- Same row updated: `DON-47D11AAA`
- Status changed to `ready`
- Active donation pointer cleared

### 3) Row contents after update
Verified sheet row:

- `DonationID`: `DON-47D11AAA`
- `DonorName`: `Anonymous Telegram donor`
- `DonorContact`: `unknown`
- `ItemDescription`: `3 coats and 2 blankets`
- `PickupOrDropoff`: `dropoff`
- `Location`: `public-safe test area`
- `AvailableDate`: `unknown`
- `Status`: `ready`
- `ReceiptNeeded`: `no`
- `ConsentToPublicThanks`: `no`

### 4) AuditLog
Verified Google Sheets audit log entries for the donation:

- `create` for `Donations/DON-47D11AAA`
- `update` for `Donations/DON-47D11AAA`

### 5) Sync and docs
Ran:

- `python scripts/sync_approved_safe_data.py`

Verified:

- `docs/data/approved_donations.json` includes `DON-47D11AAA`
- `docs/data/approved_donations.json` only exposes safe fields
- `docs` pages were regenerated from the approved-safe export
- `/daily` shows the donation once

### 6) State cleanup
Verified the active draft state file is now empty again:

- `C:\Users\fallo\AppData\Local\hermes\state\telegram_active_need_drafts.json` → `{}`

## What Failed

- Nothing blocking.

## Current Exact State

- `/donation` is live in the Telegram router.
- Donation drafts can be created without `DonationID`.
- Sloppy text is accepted and preserved as the donation description.
- Plain follow-up text attaches to the active donation draft.
- Donation drafts clear from active state when marked `ready`.
- Approved-safe donation exports do not include donor contact or private location fields.

## Remaining Blockers

- None in the code path that was requested.
- If the running Telegram gateway is a separate long-lived process, it may need a reload to pick up the new code.

## Next Actionable Step

- Reload/restart the live Telegram gateway if needed.
- Otherwise, the next logical feature would be `/donation`-specific polish or a public-safe follow-up flow, if you want it.

## Evidence Paths

- `C:\Users\fallo\non-profit-hermes-mvp\scripts\telegram_intake_router.py`
- `C:\Users\fallo\non-profit-hermes-mvp\scripts\non_profit_hermes_ops.py`
- `C:\Users\fallo\non-profit-hermes-mvp\scripts\sync_approved_safe_data.py`
- `C:\Users\fallo\non-profit-hermes-mvp\docs\data\approved_donations.json`
- `C:\Users\fallo\non-profit-hermes-mvp\docs\current-needs.html`
- `C:\Users\fallo\non-profit-hermes-mvp\docs\current-needs\index.html`
