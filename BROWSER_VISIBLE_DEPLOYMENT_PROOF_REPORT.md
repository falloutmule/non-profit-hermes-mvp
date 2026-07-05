# Browser Visible Deployment Proof Report

## What was done

- Opened the canonical public site in a real browser.
- Visited the canonical pages and captured browser-visible proof via screenshots.
- Verified the canonical home page shows:
  - `LIVE_DEPLOY_MARKER_5E15FB3_NONPROFIT_HERMES`
  - `approved-safe sync verified`
- Verified the canonical Current Needs page shows:
  - `REQ-TEST-001`
- Verified the canonical Calendar page shows:
  - `TEST - Non-Profit Hermes Calendar Wiring`
- Verified the canonical Reports page shows:
  - `REP-TEST-001`
- Verified the canonical Today page shows synced approved-safe items.
- Checked GitHub Pages source/build state after the browser proof sequence.

## What was verified

- Browser screenshot proof exists for the canonical homepage.
- Browser screenshot proof exists for Current Needs.
- Browser screenshot proof exists for Calendar.
- Browser screenshot proof exists for Reports.
- Browser screenshot proof exists for Today.
- Canonical URLs were opened directly in the browser, not via raw GitHub or local files.
- GitHub Pages source remained `main /`.

## What failed

- GitHub Pages status was still `building` when last checked in the final state capture.
- The browser proof itself, however, showed the requested marker/data in the live page body.

## Current exact state

- Repo commit on `main`: `0e0dac2 docs: finalize canonical deployment proof`
- Pages source: `main /`
- Pages status at last API check: `building`
- Canonical site: `https://falloutmule.github.io/non-profit-hermes-mvp/`

## Remaining blockers

- Wait for the current Pages build to complete before making any further deployment changes.

## Next actionable step

- Re-check the Pages build status and, if needed, re-open the canonical URLs in the browser.

## Evidence paths/files/screenshots/URLs

- `C:\Users\fallo\non-profit-hermes-mvp\BROWSER_VISIBLE_DEPLOYMENT_PROOF_REPORT.md`
- `C:\Users\fallo\AppData\Local\hermes\cache\screenshots\browser_screenshot_7db38ddb274a48d8ad5ca3660a426cff.png`
- `C:\Users\fallo\AppData\Local\hermes\cache\screenshots\browser_screenshot_4d3b7469d88f44f7aca5dc9a97a1955f.png`
- `C:\Users\fallo\AppData\Local\hermes\cache\screenshots\browser_screenshot_90d3e4174ca7477099fea8a3577bc6eb.png`
- `C:\Users\fallo\AppData\Local\hermes\cache\screenshots\browser_screenshot_baee08931a6a479cbec165dadffbc7e4.png`
- `C:\Users\fallo\AppData\Local\hermes\cache\screenshots\browser_screenshot_3de109fb74804079832e109b214b2e00.png`
- `https://falloutmule.github.io/non-profit-hermes-mvp/`
- `https://falloutmule.github.io/non-profit-hermes-mvp/current-needs`
- `https://falloutmule.github.io/non-profit-hermes-mvp/calendar`
- `https://falloutmule.github.io/non-profit-hermes-mvp/reports`
- `https://falloutmule.github.io/non-profit-hermes-mvp/today`
