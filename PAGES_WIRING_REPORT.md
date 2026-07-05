# GitHub Pages Wiring Report

## What was done

- Enabled GitHub Pages for `falloutmule/non-profit-hermes-mvp` from the `main` branch at repo root.
- Added a minimal Jekyll layout in `_layouts/default.html` for readable board-facing pages.
- Added explicit permalinks for `/`, `/today`, `/current-needs`, `/calendar`, `/volunteer`, `/donations`, `/reports`, and `/board-log`.
- Kept the site free of private data.
- Preserved the existing scaffold; no app expansion.

## What was verified

- GitHub Pages is configured for `falloutmule/non-profit-hermes-mvp` from `main` at repo root.
- The root URL returned HTTP 200.
- Each required page route returned HTTP 200:
  - `/`
  - `/today`
  - `/current-needs`
  - `/calendar`
  - `/volunteer`
  - `/donations`
  - `/reports`
  - `/board-log`

## What failed

- Initial verification attempts returned GitHub Pages 404s before the permalink/layout change was committed.
- No remaining blocker after the rebuild completed.

## Current exact state

- Repo: `https://github.com/falloutmule/non-profit-hermes-mvp`
- Git branch: `main`
- GitHub Pages source: `main` branch, `/`
- Site URL: `https://falloutmule.github.io/non-profit-hermes-mvp/`
- Layout file: `_layouts/default.html`
- Pages have explicit permalinks for all required routes.
- No private data was added.

## Remaining blockers

- None for this wiring task.

## Next actionable step

- Start wiring approved-safe data generation from Sheets/Calendar into the existing board pages.

## Evidence paths/files/logs/URLs

- `C:\Users\fallo\non-profit-hermes-mvp\_config.yml`
- `C:\Users\fallo\non-profit-hermes-mvp\_layouts\default.html`
- `C:\Users\fallo\non-profit-hermes-mvp\index.md`
- `C:\Users\fallo\non-profit-hermes-mvp\today.md`
- `C:\Users\fallo\non-profit-hermes-mvp\current-needs.md`
- `C:\Users\fallo\non-profit-hermes-mvp\calendar.md`
- `C:\Users\fallo\non-profit-hermes-mvp\volunteer.md`
- `C:\Users\fallo\non-profit-hermes-mvp\donations.md`
- `C:\Users\fallo\non-profit-hermes-mvp\reports.md`
- `C:\Users\fallo\non-profit-hermes-mvp\board-log.md`
- `C:\Users\fallo\non-profit-hermes-mvp\PAGES_WIRING_REPORT.md`
- `https://api.github.com/repos/falloutmule/non-profit-hermes-mvp/pages`
- `https://api.github.com/repos/falloutmule/non-profit-hermes-mvp/pages/builds/1079944534`
- `https://falloutmule.github.io/non-profit-hermes-mvp/`
- `https://falloutmule.github.io/non-profit-hermes-mvp/today`
- `https://falloutmule.github.io/non-profit-hermes-mvp/current-needs`
- `https://falloutmule.github.io/non-profit-hermes-mvp/calendar`
- `https://falloutmule.github.io/non-profit-hermes-mvp/volunteer`
- `https://falloutmule.github.io/non-profit-hermes-mvp/donations`
- `https://falloutmule.github.io/non-profit-hermes-mvp/reports`
- `https://falloutmule.github.io/non-profit-hermes-mvp/board-log`
