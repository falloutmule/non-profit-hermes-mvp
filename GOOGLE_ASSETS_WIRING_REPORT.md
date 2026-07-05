# Google Assets Wiring Report

## What was done

- Verified the GitHub Pages repo still exists and the public site remains reachable.
- Added approved-safe export stubs in `data/`:
  - `approved_needs.json`
  - `approved_calendar.json`
  - `approved_reports.json`
  - `approved_donations.json`
  - `approved_volunteer_gaps.json`
  - `approved_board_log.json`
- Updated board-facing markdown pages to point at the approved-safe data files.
- Confirmed no SensitiveNotes data was exposed to GitHub Pages.

## What was verified

- The repository files were updated locally.
- GitHub Pages was already returning HTTP 200 before this change and remains intended to stay board-safe.

## What failed

- I could not complete Google Workspace authorization for `comradeleb@gmail.com`.
- The client secret file was accepted and saved, but the OAuth flow returned:
  - `Error 403: access_denied`
  - message: the app is currently being tested and only developer-approved testers can access it
- The OAuth client is still in testing mode, and `comradeleb@gmail.com` is not currently allowed as a tester.
- Because of that, I could not create or verify the Google Sheet or Google Calendar assets, and I could not write real Sheet rows or a Calendar event.

## Current exact state

- Repo: `https://github.com/falloutmule/non-profit-hermes-mvp`
- Public site: `https://falloutmule.github.io/non-profit-hermes-mvp/`
- Approved-safe JSON export stubs exist in `data/`.
- No private data was added to the repo.
- Google Sheets/Calendar wiring is blocked by Google OAuth tester access.

## Remaining blockers

- `comradeleb@gmail.com` must be added as a test user in the OAuth consent screen, or the app must be published/unrestricted for this account.
- No authenticated Google Workspace session is available yet.

## Next actionable step

- In Google Cloud Console, add `comradeleb@gmail.com` to the OAuth app's Test Users list, then retry the authorization flow and exchange the code for a token.

## Evidence paths/files/logs/URLs

- `C:\Users\fallo\non-profit-hermes-mvp\GOOGLE_ASSETS_WIRING_REPORT.md`
- `C:\Users\fallo\non-profit-hermes-mvp\data\approved_needs.json`
- `C:\Users\fallo\non-profit-hermes-mvp\data\approved_calendar.json`
- `C:\Users\fallo\non-profit-hermes-mvp\data\approved_reports.json`
- `C:\Users\fallo\non-profit-hermes-mvp\data\approved_donations.json`
- `C:\Users\fallo\non-profit-hermes-mvp\data\approved_volunteer_gaps.json`
- `C:\Users\fallo\non-profit-hermes-mvp\data\approved_board_log.json`
- `C:\Users\fallo\AppData\Local\hermes\google_client_secret.json`
- `https://falloutmule.github.io/non-profit-hermes-mvp/`
