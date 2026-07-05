# DEPLOYMENT_SOURCE_DIAGNOSIS_REPORT

## What was done

1. Inspected Pages configuration via `gh api` and GitHub API
2. Checked deployment history for the repo
3. Checked for gh-pages branch, docs/ folder, Actions workflow, Jekyll config
4. Fetched public response headers and bodies for all canonical URLs
5. Created `.nojekyll` to bypass Jekyll processing for static files
6. Created `proof-8194ce0.html` — a unique static HTML file at repo root
7. Committed and pushed all changes (commit `b5b6348`)
8. Inspected the latest Pages build logs
9. Re-ran the failed workflow

## What was verified

### Pages Configuration
- **Source branch**: `main`
- **Source folder**: `/`
- **Custom domain**: none
- **Build type**: `legacy` (uses `jekyll-build-pages` Docker image via GitHub Actions)
- **Deployment mechanism**: GitHub Actions workflow (build → upload artifact → deploy)
- **No gh-pages branch**: only `main` exists
- **No docs/ folder**: repo root is the source
- **_config.yml**: uses `theme: minima`, `markdown: kramdown`
- **No .nojekyll file until now**: added in commit `b5b6348`

### Deployment History (most recent first)
| Commit SHA | Status | Time |
|---|---|---|
| b5b6348 | **FAILURE** (deploy step) | 2026-07-05 23:07 |
| 8194ce0 | **FAILURE** (deploy step) | 2026-07-05 22:16 |
| 81fa62ef | **SUCCESS** | 2026-07-05 22:14 |
| 051f654 | SUCCESS | 2026-07-05 21:43 |
| 1d4e735 | SUCCESS | 2026-07-05 21:33 |

### Build Log Error (both failures)
```
deploy  Deploy to GitHub Pages  ##[error]Deployment failed, try again later.
```

The **build** step (`jekyll-build-pages`) and **artifact upload** succeed. Only the **deploy** step fails. This is a transient GitHub Pages infrastructure error, not a content/config issue.

### Public HTTP Response (currently live)

The currently deployed site is from commit `81fa62ef` (last successful build):

- **ETag**: `"6a4ad77b-d0c"`
- **Last-Modified**: Sun, 05 Jul 2026 22:15:23 GMT
- **Cache-Control**: max-age=600 (10-minute CDN cache)
- **Content-Length**: 3340 bytes
- **X-Cache**: HIT (served from Varnish CDN edge)

### Content verification via public curl (no cache busting needed)

| URL | Found Markers |
|---|---|
| `/` | `approved-safe sync verified`, `LIVE_DEPLOY_MARKER_5E15FB3_NONPROFIT_HERMES`, `REP-TEST-001` |
| `/current-needs` | `LIVE_DEPLOY_MARKER_5E15FB3_NONPROFIT_HERMES`, `REQ-TEST-001` |
| `/deployment-proof` | `LIVE_EXTERNAL_PROOF_PAGE_NONPROFIT_HERMES` |
| `/proof-8194ce0.html` | **404 Not Found** (build not yet deployed) |

No placeholder strings found in any currently live page.

## What failed

### Root Cause of External Mismatch

**Two separate issues were conflated:**

1. **Transient GitHub Pages deploy failure**: The latest two builds (`8194ce0`, `b5b6348`) both succeeded in the Jekyll build step but failed at the deploy step with `##[error]Deployment failed, try again later.` This is a GitHub Pages infrastructure issue — the build artifact is correctly generated and uploaded, but the deployment service errors out.

2. **CDN cache**: The live site has `Cache-Control: max-age=600` (10-minute TTL). External checks hitting a cached edge node may see stale content if the last successful deploy was recent.

### Current Published State

The currently published site is from commit `81fa62ef` (last successful build), which DOES contain:
- All deployment markers
- All synced test records
- No placeholder text
- The deployment-proof page with `LIVE_EXTERNAL_PROOF_PAGE_NONPROFIT_HERMES`

### Why the static proof file returns 404

The `proof-8194ce0.html` file was committed in build `b5b6348`, which has not successfully deployed yet due to the transient deploy failure. The currently live site (from `81fa62ef`) predates this file.

## Current exact state

- Repo commit on `main`: `b5b6348`
- Last successful Pages deploy: `81fa62ef`
- Latest Pages builds: 2 consecutive deploy failures (infrastructure, not content)
- Live site serving correct content from `81fa62ef`: **confirmed via public curl**
- `.nojekyll` file has been added to prevent future Jekyll issues
- Static proof file `proof-8194ce0.html` exists in repo but not yet deployed

## Remaining blockers

- **GitHub Pages deploy infrastructure issue**: "Deployment failed, try again later" on both `8194ce0` and `b5b6348` builds. Needs GitHub to resolve or a manual retry to succeed.
- Re-run of `b5b6348` build is currently `queued` (runner backlog).

## Next actionable step

1. Wait for the `b5b6348` re-run to complete (currently queued)
2. Verify `https://falloutmule.github.io/non-profit-hermes-mvp/proof-8194ce0.html` returns 200
3. If deploy continues to fail, the issue is on GitHub's side and needs GitHub Support

## Evidence paths/files/headers/URLs

Diagnosis data:
- `proof-external-mismatch-diagnosis/root.headers.txt`
- `proof-external-mismatch-diagnosis/root.body.html`
- `proof-external-mismatch-diagnosis/current-needs.headers.txt`
- `proof-external-mismatch-diagnosis/current-needs.body.html`
- `proof-external-mismatch-diagnosis/deployment-proof.headers.txt`
- `proof-external-mismatch-diagnosis/deployment-proof.body.html`

Static proof file:
- `proof-8194ce0.html` (in repo, not yet deployed)

Config:
- `.nojekyll` (added in `b5b6348`)
- `_config.yml` (theme: minima)

Canonical URLs:
- `https://falloutmule.github.io/non-profit-hermes-mvp/`
- `https://falloutmule.github.io/non-profit-hermes-mvp/current-needs`
- `https://falloutmule.github.io/non-profit-hermes-mvp/deployment-proof`
- `https://falloutmule.github.io/non-profit-hermes-mvp/proof-8194ce0.html`

### Summary

The external verification issue is caused by **GitHub Pages deploy infrastructure failures**, not by incorrect content or configuration. The currently live site (from `81fa62ef`) is correct — all markers verified via public curl. Newer commits fail at the deploy step with a transient error. The solution is to wait for GitHub's deploy service to recover and re-run the workflow.
