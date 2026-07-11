# Architecture — Non-Profit Hermes MVP

**Last updated:** 2026-07-11 (CLEANUP-001)

## System overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Telegram (user input)                     │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Hermes Gateway + Plugins (external to this repo)            │
│                                                               │
│  non-profit-hermes-daily       → /daily                      │
│  non-profit-hermes-need         → /need                      │
│  non-profit-hermes-donation     → /donation                  │
│  non-profit-hermes-report       → /report                    │
│  non-profit-hermes-task         → /task                      │
│  non-profit-hermes-inventory    → /inventory                 │
│  non-profit-hermes-event        → /event (draft-only)        │
└──────────────────────────┬──────────────────────────────────┘
                           │ delegates to
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  scripts/telegram_intake_router.py                           │
│                                                               │
│  • Draft-first intake for all commands                       │
│  • Active-draft state tracking (per chat scope)              │
│  • Follow-up routing (event→report→task→inventory→donation→need) │
│  • /daily summary builder (currently calls sync, which     │
│    writes docs/ files; does not commit/push; read-only    │
│    no-mutation is the cleanup target)                      │
│  • Source-scope bridge: telegram:live → telegram:<chat_id>   │
└─────────────┬───────────────────────────────┬───────────────┘
              │ writes via                    │ reads via
              ▼                               ▼
┌──────────────────────────┐  ┌────────────────────────────────┐
│  scripts/                │  │  scripts/                       │
│  non_profit_hermes_ops   │  │  sync_approved_safe_data.py     │
│  .py                     │  │                                │
│                          │  │  • Reads Sheets + Calendar     │
│  • add_request           │  │  • Filters to approved-safe    │
│  • add_donation          │  │  • Writes docs/ HTML + JSON    │
│  • add_report            │  │  • Privacy gates per type      │
│  • add_task              │  └────────────────────────────────┘
│  • update_inventory      │
│  • upsert_event_draft    │
│  • update_event_draft    │
│  • create_calendar_event │
│  • create_calendar_event │
│    _from_draft (disabled)│
│  • write_audit_log       │
└───────────┬──────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────┐
│              Google Sheets (system of record)                 │
│                                                               │
│  Requests │ Donations │ Reports │ Tasks │ Inventory          │
│  CalendarLog │ AuditLog │ (SensitiveNotes - logical)         │
└─────────────────────────────────────────────────────────────┘
            │
            ▼ (CalendarLog promotion only, EVENT-004)
┌─────────────────────────────────────────────────────────────┐
│              Google Calendar (dated commitments)              │
│  Currently disabled for /event. Live promotion from a      │
│  draft is untested. Historical safe fake direct backend    │
│  test events exist. EVENT-004 authorizes first live        │
│  promotion from a draft.                                    │
└─────────────────────────────────────────────────────────────┘

                           │ sync output
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  docs/ (GitHub Pages — main /docs)                           │
│                                                               │
│  index.html │ today.html │ current-needs.html                │
│  calendar.html │ reports.html │ deployment-proof.html        │
│  data/approved_*.json                                        │
│                                                               │
│  Public URL: https://falloutmule.github.io/non-profit-hermes │
│  -mvp/                                                       │
└─────────────────────────────────────────────────────────────┘
```

## Component responsibilities

### Hermes plugins (external)

Each plugin lives under `~/.hermes/plugins/non-profit-hermes-<cmd>/` and contains:

- `plugin.yaml` — kind: standalone, registers the command
- `__init__.py` — entrypoint, calls the router, renders via `_result_to_text()`

Plugins are **thin shims**. They contain no business logic, no direct Sheets/Calendar writes. They delegate to `scripts/telegram_intake_router.py`.

### `scripts/telegram_intake_router.py`

The router is the intelligence layer:

- **Draft-first intake**: all write commands create a `needs-info` draft first, then accept follow-up text to complete it.
- **Active-draft state**: per-chat pointers track which draft a follow-up should attach to. State stored in `telegram_active_need_drafts.json`.
- **Follow-up chain**: `handle_message()` tries event → report → task → inventory → donation → need in order. Each handler returns `None` (pass-through) if the message lacks command-specific fields and no active draft exists.
- **`/daily`**: currently calls the sync script, which writes `docs/` files (does not commit or push them). Read-only no-mutation behavior is the cleanup target. Displays calendar, needs, donations, reports, volunteer gaps, inventory shortages, website links, and completed-item counts.
- **Source-scope bridge**: maps `telegram:live` → `telegram:6080816249` for legacy plugin compatibility.

### `scripts/non_profit_hermes_ops.py`

The backend module. Every write operation:

1. Calls `ensure_header()` to sync the Sheet header row with the code schema.
2. Writes the data row.
3. Calls `write_audit_log()` to record actor, action, target, before/after, result.

Key operations: `add_request`, `add_donation`, `add_report`, `add_task`, `update_inventory`, `upsert_event_draft`, `update_event_draft`, `create_calendar_event`, `create_calendar_event_from_draft`, `write_audit_log`.

### `scripts/sync_approved_safe_data.py`

The publication pipeline. Reads Sheets + Calendar, filters to approved-safe records, generates self-contained HTML pages and JSON exports under `docs/`.

Privacy filters per type:
- **Requests**: `PrivacyLevel` in approved set (board-visible, public-safe, board-visible-test). **Note:** `ConsentToShare` and `Status` checks not yet implemented (P0 gap).
- **Reports**: exclude `private-review`, `private-hold`, `draft`, `needs-info`
- **Donations**: exports safe fields only (no donor contact or private location)
- **Calendar**: two-source join — CalendarLog approval gate + live Calendar ID existence check
- **Board log**: audit entries (currently exposes internal IDs — P0 cleanup item)

### `docs/` (GitHub Pages)

Static HTML/JSON output. Pages source: `main /docs` (verified). All pages carry the deployment marker `CLEAN_DOCS_DEPLOY_NON_PROFIT_HERMES_002`.

## Data flow: write path

```
User types /need "diapers size 4"
  → plugin delegates to router
  → router creates draft (REQ-XXXXXXXX, status=needs-info)
  → backend add_request() writes Requests row + AuditLog row
  → router sets active_need_request_id in state
  → router returns "Draft created, missing: contact, urgency, ..."

User sends follow-up "contact=unknown urgency=high status=ready"
  → router detects active draft
  → backend update_request() updates same row + AuditLog
  → router clears active pointer
  → router returns "Updated, status=ready"
```

## Data flow: publication path

```
Operator runs sync_approved_safe_data.py
  → reads all Sheets tabs
  → filters to approved-safe records
  → generates docs/*.html + docs/data/*.json
  → operator reviews diffs
  → operator commits and pushes

/daily (currently mutates docs/)
  → calls sync script internally
  → writes docs/*.html + docs/data/*.json
  → does NOT commit or push those files
  → read-only no-mutation is the cleanup target
```

## Privacy boundaries

| Layer | What crosses | What stays |
|-------|-------------|-----------|
| Telegram → Sheets | structured intake fields | SensitiveDetails always empty |
| Sheets → docs/ | approved-safe fields only | donor contact, private location, raw IDs, drafts |
| Sheets → Calendar | only approved+ready event drafts (EVENT-004) | private titles, descriptions, locations |
| AuditLog → board log | aggregate counts (target: cleanup) | raw audit IDs, task/inventory IDs (target: cleanup) |

See [SECURITY_AND_PRIVACY.md](SECURITY_AND_PRIVACY.md) for the full privacy model.
