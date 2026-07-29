# Security and Privacy — Non-Profit Hermes MVP

**Current security boundary captured:** 2026-07-21

Privacy is a hard gate. Google Sheets is the private system of record; GitHub Pages is a filtered public surface. Runtime/profile secrets and private records are never documentation evidence.

## Never commit or publish

- Telegram tokens or token fingerprints
- bot numeric identifiers
- raw private chat or user identifiers
- OAuth access/refresh tokens, authorization codes, callback payloads, PKCE material, client secrets, or authorization headers
- private Google Sheet rows or Calendar details
- exact private locations, addresses, phone numbers, or identifying photos
- medical, addiction, legal, family-crisis, immigration, police, or interpersonal-conflict details
- credential files, `.env`, `auth.json`, sessions, memories, state databases, or logs

Documentation uses placeholders such as `<hermes-home>`, `<nonprofit-profile>`, and `<plugin-root>` instead of local secret-bearing paths.

## Profile isolation

The authoritative profile is `nonprofit`, with bot identity `@HnonProfitBOT` and model route `openai-codex/gpt-5.6-sol`. The seven nonprofit plugins are enabled only in that profile and disabled in `default`. Different profiles are separate trust domains; do not copy or compare credentials across them in public evidence.

Read-only identity and command-registry checks may emit only allowlisted fields such as bot username and command names. Current documentation intentionally omits token-derived fingerprints, numeric bot IDs, and raw chat IDs even if older restricted evidence contains them.

## Private intake and audit

The write commands are draft-first and private by default:

- Requests, Donations, Reports, and Events begin in private review.
- Tasks and Inventory are internal-only.
- Automated report writes keep sensitive-detail fields empty.
- Every supported Google mutation writes an AuditLog entry.
- Missing facts remain unknown; they are not inferred.

A command being registered does not authorize or prove a live write. The nonprofit gateway is currently stopped.

## Deny-by-default public exports

Approved-safe export requires all applicable gates:

- Requests: approved privacy, allowed public status, affirmative consent
- Donations: approved privacy, allowed public status, affirmative listing permission
- Reports: approved privacy, allowed public status, affirmative summary permission, non-empty approved public summary
- Calendar: approved CalendarLog record and matching live event
- Board log: aggregate-only output
- Tasks and Inventory: never public

Newest-record deduplication occurs before public gates, so a newer private/draft duplicate suppresses an older public candidate. Public HTML escapes user-controlled values.

## `/daily` boundary

`/daily` collects the approved-safe snapshot in memory. It does not:

- write Sheets or Calendar;
- generate or modify `docs/`;
- commit, push, or publish;
- persist an OAuth refresh.

The focused fake-based read-only tests pass. Historical human-originated `/daily` evidence dated 2026-07-12 is retained, but current live transport/zero-write acceptance is untested because the gateway is stopped.

## Calendar boundary

`/event` creates or updates a CalendarLog draft. Calendar creation requires a separate authorization for the exact draft, preflight and scope guards, authorization consumption immediately before the external attempt, same-row event-ID persistence, idempotent retry behavior, and privacy exclusion verification.

Historical EVENT-004 evidence records one controlled promotion. It is not reusable authority for another event, public-calendar inclusion, gateway activation, or publication.

## OAuth credential persistence

Operational loaders use atomic and recoverable durable refresh:

1. refresh only the in-memory credential;
2. serialize a separate candidate;
3. validate credential, scope, client identity, JSON shape, hash, and ACL invariants;
4. acquire an exclusive lock;
5. create and flush an exact-byte backup;
6. atomically replace the operational token;
7. verify the promoted hash and ACL;
8. remove backup/temporary state on success or restore exact bytes and ACL on handled post-swap failure.

`/daily` and sync `--dry-run` use in-memory refresh only. Error evidence contains stable codes and hashes, never credential values.

## Plugin installation and backups

The plugin installer verifies canonical hashes, requires explicit `--apply` and `--target-root`, and requires a second `--live` consent for the live shared root. It creates a timestamped backup before replacing an existing plugin directory and restores that backup if staged replacement fails.

Plugin backups are source/runtime artifacts, not credential backups. Do not place secrets in plugin directories or copy profile state into installer backups. Retention and deletion require a separate decision.

## Publication boundary

`sync_approved_safe_data.py --dry-run` reads and classifies but does not write public files. Running without `--dry-run` generates `docs/`; it does not authorize publication. Human review and explicit authorization are required for the exact generated diff before commit or push.

The 2026-07-21 inventory did not regenerate or publish the site. Public-generation parity remains untested in that inventory.

## Current risks and pending work

- The gateway is stopped; current live dispatch and human canaries are unverified.
- Port config and launcher override differ, and gateway metadata is stale.
- Operational scripts and legacy plugin entrypoints contain user-specific paths and `sys.path` mutation.
- Dependencies and profile installation are not packaged.
- The unified plugin, profile distribution, runtime doctor, and clean-install acceptance do not exist yet.
- Historical reports can contain bounded identifiers or obsolete permissions; use the current canonical docs and reports supersession map before relying on them.
