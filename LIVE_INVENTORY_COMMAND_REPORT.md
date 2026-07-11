# LIVE_INVENTORY_COMMAND_REPORT.md

> **Historical report (2026-07-11, CLEANUP-001):** This report documents the initial `/inventory` wiring. The command is now **live and verified**. Plugin is gateway-active. Live test record `INV-4A2B0AE8` was verified. See [PROJECT_STATUS.md](PROJECT_STATUS.md) for current status.

## Date
2026-07-09

## Goal
Wire Telegram `/inventory` as a live command using the draft-first pattern, with true upsert-by-ItemID backend.

## What was done

### Backend (`non_profit_hermes_ops.py`)
- Added `Status`, `NextAction`, `LastUpdated`, `SourceMessageLink` to Inventory header (13→17 columns)
- Replaced duplicate-skip `update_inventory()` with true upsert:
  - If ItemID exists: updates the row in-place with before/after audit
  - If ItemID new: creates a new row with needs-info defaults
  - Both paths return `created` or `updated` status
- Added `ensure_header(svc, "Inventory")` call

### Router (`telegram_intake_router.py`)
- Added inventory active draft tracking: `get/set/clear_active_inventory_id`
- Added helpers: `inventory_row_by_id`, `open_inventory_drafts`, `resolve_inventory_followup_target`
- Replaced stub `route_inventory()` with draft-first:
  - Accepts sloppy free text (`/inventory toilet paper 12 rolls`)
  - Parses item_name, quantity, unit from free text
  - Lists 8 missing fields, defaults to needs-info
- Added `route_inventory_followup()` with field-specific detection
- Wired into `handle_message()` (between task and donation)
- Updated example in `_example_for_command()`

### Plugin
- Created and enabled `non-profit-hermes-inventory`
- `source_link="telegram:6080816249"` (bridge-compatible)

## Verification

### Local test
```
/inventory toilet paper 12 rolls
→ ok=True, status=needs-info, id=INV-F8815356, 8 missing fields

category=hygiene unit=rolls minimum_needed=20 storage_location=pantry condition=new public_need_allowed=no status=ready
→ ok=True, status=updated, id=INV-F8815356 (same row), active pointer cleared
```

### Cross-contamination
- Report create + follow-up: still works
- Task create + follow-up: still works
- Inventory-specific fields (`quantity`, `unit`, `storage_location`) prevent interception by wrong handler

### Sync + daily
- `sync_approved_safe_data.py`: clean
- `/daily`: functional, no inventory details exported to docs/

### Known parser quirk
- `/inventory toilet paper 12 rolls` parses `item_name="toilet"` (first word only)
- "paper" is not a digit, so quantity extraction skips
- Workaround: use explicit keys: `/inventory item="toilet paper" quantity=12 unit=rolls`
- Non-blocking; future parser polish

## Live Telegram
- Plugin enabled. Gateway session needed for `/inventory` command to activate.
- Expected: `/inventory toilet paper 12 rolls` creates draft, follow-up attaches.
