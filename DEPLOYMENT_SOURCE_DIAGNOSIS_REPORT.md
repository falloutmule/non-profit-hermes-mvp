# DEPLOYMENT_SOURCE_DIAGNOSIS_REPORT

## What was done

1. Inspected Pages configuration via `gh api`
2. Checked deployment history for the repo
3. Analyzed Pages build logs for the failures
4. Fetched public response headers and bodies for all canonical URLs
5. Created `.nojekyll` — later reverted (broke .md → .html conversion)
6. Created `proof-8194ce0.html` — unique static HTML proof file at repo root
7. Committed and pushed changes
8. Monitored GitHub Pages builds until success
9. Verified all URLs return 200 with correct content via public curl

## What was verified

### Pages Configuration
- **Source branch**: `main`
- **Source folder**: `/`
- **Custom domain**: none
- **Build type**: `legacy` (uses `jekyll-build-pages` Docker image via GitHub Actions)
- **No gh-pages branch**, no **docs/** folder
- **_config.yml**: `theme: minima`, `markdown: kramdown` — works correctly

### Deployment History
| Commit | Status | Time (UTC) |
|---|---|---|
| 6b310d8 | **SUCCESS** | 2026-07-05 23:14+ |
| 134287c | SUCCESS | 2026-07-05 23:14 |
| b5b6348 | (rerun) | 2026-07-05 23:07 |
| 8194ce0 | FAILURE (deploy step) | 2026-07-05 22:16 |
| 81fa62ef | SUCCESS | 2026-07-05 22:14 |

### Root Cause of Mismatch

**The Jekyll build step always succeeded.** The deploy step had transient failures:

```
deploy  Deploy to GitHub Pages  ##[error]Deployment failed, try again later.
```

Two consecutive builds (`8194ce0`, `b5b6348`) generated correct build artifacts but the deploy step errored with a transient GitHub Pages infrastructure failure. The site fell back to the last successful deploy (`81fa62ef`), which was still serving correct content.

Additionally, adding `.nojekyll` caused `index.md` to not be converted to `index.html`, making the root return 404 on the subsequent build. This was fixed by removing `.nojekyll`.

### Current Live Content (commit 6b310d8)

| URL | Status | Key markers found |
|---|---|---|
| `/` | 200 OK | `LIVE_DEPLOY_MARKER_5E15FB3_NONPROFIT_HERMES`, `approved-safe sync verified`, `REP-TEST-001` |
| `/current-needs` | 200 OK | `LIVE_DEPLOY_MARKER_5E15FB3_NONPROFIT_HERMES`, `REQ-TEST-001` |
| `/deployment-proof` | 200 OK | `LIVE_EXTERNAL_PROOF_PAGE_NONPROFIT_HERMES` |
| `/proof-8194ce0.html` | 200 OK | `UNIQUE_STATIC_HTML_PROOF_8194CE0_NONPROFIT_HERMES` |

No placeholder strings found in any page.

## What failed (resolved)

1. **Transient GitHub Pages deploy failures** — Two builds failed at the deploy step with `##[error]Deployment failed, try again later.`. This is a GitHub Pages infrastructure issue that resolved after retries.
2. **`.nojekyll` breakage** — Adding `.nojekyll` stopped Jekyll from converting `.md` to `.html`, causing the root to return 404. Fixed by removing `.nojekyll`.

## Current exact state

- Repo commit on `main`: `6b310d8`
- Last Pages build: **SUCCESS**
- All 4 test URLs return 200 OK with correct content
- Proof file live at `/proof-8194ce0.html`

## Remaining blockers

None. The deployment is live and verified.

## Next actionable step

Proceed to next MVP phase as desired.

## Evidence paths/files/headers/URLs

Diagnosis data:
- `proof-external-mismatch-diagnosis/root.headers.txt`
- `proof-external-mismatch-diagnosis/root.body.html`
- `proof-external-mismatch-diagnosis/current-needs.body.html`
- `proof-external-mismatch-diagnosis/deployment-proof.body.html`

Proof files:
- `proof-8194ce0.html` (live at `/proof-8194ce0.html`)
- `proof-browser-screenshots/` (6 screenshots)
- `proof-browser-source/` (6 page sources)

Live URLs:
- `https://falloutmule.github.io/non-profit-hermes-mvp/`
- `https://falloutmule.github.io/non-profit-hermes-mvp/current-needs`
- `https://falloutmule.github.io/non-profit-hermes-mvp/calendar`
- `https://falloutmule.github.io/non-profit-hermes-mvp/reports`
- `https://falloutmule.github.io/non-profit-hermes-mvp/today`
- `https://falloutmule.github.io/non-profit-hermes-mvp/deployment-proof`
- `https://falloutmule.github.io/non-profit-hermes-mvp/proof-8194ce0.html`
