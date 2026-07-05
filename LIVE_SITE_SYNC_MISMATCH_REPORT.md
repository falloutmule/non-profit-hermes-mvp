# Live Site Sync Mismatch Report

## What was done

- Verified local git state and remote state.
- Verified local Markdown pages contain the approved-safe sync test strings.
- Verified raw GitHub content on `main` contains the same strings.
- Verified GitHub Pages source is `main` at repo root and the latest build is built for commit `fc2aa11`.
- Verified the live public site serves the approved-safe synced content.
- Kept the site scope unchanged and avoided private data or SensitiveNotes exposure.

## What was verified

- `git status` is clean.
- Local HEAD: `fc2aa11 feat: render approved safe sync data on pages`.
- Branch: `main`.
- Remote origin points to `falloutmule/non-profit-hermes-mvp`.
- Remote `main` resolves to commit `fc2aa119463dfd9c66eeb5420c6e0b40a922e5f1`.
- Local files contain:
  - `approved-safe sync verified`
  - `REQ-TEST-001`
  - `TEST - Non-Profit Hermes Calendar Wiring`
  - `REP-TEST-001`
- Raw GitHub `main` content contains the same strings.
- Pages source: `main /`.
- Latest Pages build status: `built`.
- Latest Pages build commit: `fc2aa119463dfd9c66eeb5420c6e0b40a922e5f1`.
- Live HTTP content contains the synced data:
  - `/` has `approved-safe sync verified`
  - `/current-needs` has `REQ-TEST-001`
  - `/calendar` has `TEST - Non-Profit Hermes Calendar Wiring`
  - `/reports` has `REP-TEST-001`
  - `/today` contains synced approved-safe content

## What failed

- The earlier external check had shown stale content, but that mismatch is no longer present after verifying the live site and rebuild.

## Current exact state

- Repo commit on `main`: `fc2aa11 feat: render approved safe sync data on pages`
- Pages source: `main /`
- Pages build: `built`
- Site URL: `https://falloutmule.github.io/non-profit-hermes-mvp/`

## Remaining blockers

- None for the mismatch investigation.

## Next actionable step

- None required unless further automation is requested later.

## Evidence paths/files/logs/URLs

- `C:\Users\fallo\non-profit-hermes-mvp\LIVE_SITE_SYNC_MISMATCH_REPORT.md`
- `C:\Users\fallo\non-profit-hermes-mvp\index.md`
- `C:\Users\fallo\non-profit-hermes-mvp\today.md`
- `C:\Users\fallo\non-profit-hermes-mvp\current-needs.md`
- `C:\Users\fallo\non-profit-hermes-mvp\calendar.md`
- `C:\Users\fallo\non-profit-hermes-mvp\reports.md`
- `https://raw.githubusercontent.com/falloutmule/non-profit-hermes-mvp/main/index.md`
- `https://raw.githubusercontent.com/falloutmule/non-profit-hermes-mvp/main/today.md`
- `https://raw.githubusercontent.com/falloutmule/non-profit-hermes-mvp/main/current-needs.md`
- `https://raw.githubusercontent.com/falloutmule/non-profit-hermes-mvp/main/calendar.md`
- `https://raw.githubusercontent.com/falloutmule/non-profit-hermes-mvp/main/reports.md`
- `https://falloutmule.github.io/non-profit-hermes-mvp/`
- `https://falloutmule.github.io/non-profit-hermes-mvp/current-needs`
- `https://falloutmule.github.io/non-profit-hermes-mvp/calendar`
- `https://falloutmule.github.io/non-profit-hermes-mvp/reports`
- `https://falloutmule.github.io/non-profit-hermes-mvp/today`
