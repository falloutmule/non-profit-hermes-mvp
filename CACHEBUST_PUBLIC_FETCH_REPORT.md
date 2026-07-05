# Cachebust Public Fetch Report

## What was done

- Confirmed the committed proof files are present on `main` and pushed.
- Provided raw GitHub URLs for the committed proof files.
- Fetched the public GitHub Pages URLs again with cache-busting query strings.
- Saved the cache-busted public HTML responses into `proof-live-fetch-cachebust/`.
- Searched the saved public fetch files for required proof strings and placeholder text.

## What was verified

- Committed proof files exist in the repo history:
  - `proof-live-fetch/root.html`
  - `proof-live-fetch/current-needs.html`
  - `proof-live-fetch/calendar.html`
  - `proof-live-fetch/reports.html`
  - `proof-live-fetch/today.html`
  - `LIVE_PUBLIC_FETCH_PROOF_REPORT.md`
- The cache-busted public HTML saved files contain the required strings:
  - `approved-safe sync verified`
  - `REQ-TEST-001`
  - `TEST - Non-Profit Hermes Calendar Wiring`
  - `REP-TEST-001`
- The cache-busted public HTML saved files do not contain the placeholder phrases listed in the request.

## What failed

- No blocking failure was found in the fetched public HTML.
- The earlier external placeholder observation was not reproduced in the cache-busted public fetches.

## Current exact state

- Commit on `main`: `11091b3 docs: save live public fetch proof`
- Cache-busted proof directory: `proof-live-fetch-cachebust/`
- Live public GitHub Pages fetches show the approved-safe synced content.

## Remaining blockers

- None for this proof step.

## Next actionable step

- None required unless you want additional verification with a browser screenshot or a fresh timing pass.

## Evidence paths/files/logs/URLs

- `C:\\Users\\fallo\\non-profit-hermes-mvp\\proof-live-fetch\\root.html`
- `C:\\Users\\fallo\\non-profit-hermes-mvp\\proof-live-fetch\\current-needs.html`
- `C:\\Users\\fallo\\non-profit-hermes-mvp\\proof-live-fetch\\calendar.html`
- `C:\\Users\\fallo\\non-profit-hermes-mvp\\proof-live-fetch\\reports.html`
- `C:\\Users\\fallo\\non-profit-hermes-mvp\\proof-live-fetch\\today.html`
- `C:\\Users\\fallo\\non-profit-hermes-mvp\\proof-live-fetch-cachebust\\root.html`
- `C:\\Users\\fallo\\non-profit-hermes-mvp\\proof-live-fetch-cachebust\\current-needs.html`
- `C:\\Users\\fallo\\non-profit-hermes-mvp\\proof-live-fetch-cachebust\\calendar.html`
- `C:\\Users\\fallo\\non-profit-hermes-mvp\\proof-live-fetch-cachebust\\reports.html`
- `C:\\Users\\fallo\\non-profit-hermes-mvp\\proof-live-fetch-cachebust\\today.html`
- Raw GitHub proof URLs:
  - `https://raw.githubusercontent.com/falloutmule/non-profit-hermes-mvp/main/proof-live-fetch/root.html`
  - `https://raw.githubusercontent.com/falloutmule/non-profit-hermes-mvp/main/proof-live-fetch/current-needs.html`
  - `https://raw.githubusercontent.com/falloutmule/non-profit-hermes-mvp/main/proof-live-fetch/calendar.html`
  - `https://raw.githubusercontent.com/falloutmule/non-profit-hermes-mvp/main/proof-live-fetch/reports.html`
  - `https://raw.githubusercontent.com/falloutmule/non-profit-hermes-mvp/main/proof-live-fetch/today.html`
  - `https://raw.githubusercontent.com/falloutmule/non-profit-hermes-mvp/main/LIVE_PUBLIC_FETCH_PROOF_REPORT.md`
  - `https://raw.githubusercontent.com/falloutmule/non-profit-hermes-mvp/main/CACHEBUST_PUBLIC_FETCH_REPORT.md`
