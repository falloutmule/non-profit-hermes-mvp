# Live Public Fetch Proof Report

## What was done

- Fetched the live public GitHub Pages HTML for:
  - `/`
  - `/current-needs`
  - `/calendar`
  - `/reports`
  - `/today`
- Saved the fetched HTML to:
  - `proof-live-fetch/root.html`
  - `proof-live-fetch/current-needs.html`
  - `proof-live-fetch/calendar.html`
  - `proof-live-fetch/reports.html`
  - `proof-live-fetch/today.html`
- Searched only those saved public fetch files for required strings and placeholder strings.
- Verified the fetched public HTML contains the approved-safe synced records.

## What was verified

- `root.html` contains `approved-safe sync verified`
- `current-needs.html` contains `REQ-TEST-001`
- `calendar.html` contains `TEST - Non-Profit Hermes Calendar Wiring`
- `reports.html` contains `REP-TEST-001`
- `today.html` contains synced approved-safe content
- The saved public fetch files do **not** contain these placeholder phrases:
  - `Last update: unknown`
  - `Current state: scaffolded and published`
  - `Approved-safe current needs go here`
  - `Approved-safe board-visible calendar items go here`
  - `Approved-safe summaries go here`
  - `Approved-safe current-day summary goes here`

## What failed

- No blocking failure in the fetched public HTML proof.

## Current exact state

- Public HTML fetched from live site shows the synced approved-safe content.
- Public HTML saved under `proof-live-fetch/` proves the live site is no longer on the placeholder content.

## Remaining blockers

- None for this proof step.

## Next actionable step

- None required unless you want further changes.

## Evidence paths/files/logs/URLs

- `C:\Users\fallo\non-profit-hermes-mvp\proof-live-fetch\root.html`
- `C:\Users\fallo\non-profit-hermes-mvp\proof-live-fetch\current-needs.html`
- `C:\Users\fallo\non-profit-hermes-mvp\proof-live-fetch\calendar.html`
- `C:\Users\fallo\non-profit-hermes-mvp\proof-live-fetch\reports.html`
- `C:\Users\fallo\non-profit-hermes-mvp\proof-live-fetch\today.html`
- `https://falloutmule.github.io/non-profit-hermes-mvp/`
- `https://falloutmule.github.io/non-profit-hermes-mvp/current-needs`
- `https://falloutmule.github.io/non-profit-hermes-mvp/calendar`
- `https://falloutmule.github.io/non-profit-hermes-mvp/reports`
- `https://falloutmule.github.io/non-profit-hermes-mvp/today`
