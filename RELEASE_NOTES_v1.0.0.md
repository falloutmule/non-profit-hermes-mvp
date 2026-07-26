# Non-Profit Hermes v1.0.0 — release candidate notes

> **Status:** local release candidate. This document becomes GitHub release notes only after the branch is pushed, reviewed, merged, tagged `v1.0.0`, and released.

## What it is

Non-Profit Hermes is a separate, versioned Hermes profile distribution for Telegram-first nonprofit operations. It is installed on top of Hermes Agent; it does not replace or fork Hermes core.

## Included capabilities

- Importable `non_profit_hermes` Python package.
- Secret-free root-level Hermes profile distribution.
- One unified `non-profit-hermes` plugin registering seven commands:
  - `/daily`
  - `/need`
  - `/donation`
  - `/report`
  - `/task`
  - `/inventory`
  - `/event`
- Deterministic offline and live-readonly runtime doctor.
- Seven deprecated compatibility shims retained for one release as rollback material; they must not be enabled with the unified plugin.

## Verification

Accepted disposable clean-install run: `NPH-V1-060N-20260726073936`.

```text
23/23 acceptance stages passed
379 tests passed
69 subtests passed
production_touched: false
```

The acceptance run did not touch production. It is not proof of a live Telegram, Google, Calendar, or website integration.

## Requirements and installation

- Hermes Agent `>=0.18.2`
- Python `>=3.11`

After the future `v1.0.0` tag is published:

```bash
python -m pip install "git+https://github.com/falloutmule/non-profit-hermes-mvp.git@v1.0.0"
```

Install the profile from an inspected checkout of the tagged revision, then configure private local values separately. The distribution contains no Telegram token, OAuth credential, Google resource identifier, local account identifier, or runtime state.

```bash
hermes profile install . --name nonprofit
python -m non_profit_hermes.doctor --profile nonprofit --offline --strict
```

## Update and rollback overview

Hermes core updates and Non-Profit Hermes updates are independent:

- **Hermes core:** back up the nonprofit profile, perform the normal supported Hermes update, then run the nonprofit doctor and `/commands` and read-only `/daily` canaries.
- **Non-Profit Hermes:** use a reviewed release tag, update a staging profile, run doctor/canaries, then perform an explicitly approved live migration.
- **Rollback:** stop only the nonprofit profile, restore the prior tagged package or pre-migration backup and launcher settings, restart, then rerun `/commands` and read-only `/daily`.

Production must be pinned to a reviewed tag, never a moving branch.

## Known untested production areas

- Current production profile migration from the manually assembled profile.
- Current gateway start and exact port ownership.
- Human-originated Telegram `/commands` and `/daily` canaries.
- Live Google/Calendar read-only doctor probes and zero-write evidence.
- Published GitHub release artifact installation.
- Observation-window stability after cutover.

## Privacy

Private credentials and operational state remain local. `/daily` is designed as a read-only, board-safe summary; public generation and publication remain separate approved actions.
