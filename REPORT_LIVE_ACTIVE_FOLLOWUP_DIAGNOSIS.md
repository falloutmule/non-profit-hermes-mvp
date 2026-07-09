# REPORT_LIVE_ACTIVE_FOLLOWUP_DIAGNOSIS.md

## Date
2026-07-09

## Exact cause: Case E — gateway running old plugin code

### Evidence from state file

`C:\Users\fallo\AppData\Local\hermes\state\telegram_active_need_drafts.json`:

```json
"telegram:live": {
    "active_report_id": "REP-8BD6B07D",
    "updated_at": "2026-07-09T16:51:30"
}
```

The live gateway wrote the active draft under scope `"telegram:live"` — the OLD plugin source_link. The on-disk plugin had already been updated to `"telegram:6080816249"`, but the gateway process (PID 1868) was never restarted, so it still runs the old code.

### Scope mismatch chain

| Path | source_link | source_scope result |
|------|------------|-------------------|
| Old plugin (live) | `telegram:live` | `telegram:live` (not normalized) |
| New plugin (disk) | `telegram:6080816249` | `telegram:6080816249` |
| Gateway follow-up | `telegram:6080816249:msg:thread` | `telegram:6080816249` (after fix) |

Before this fix, `source_scope("telegram:live")` returned `"telegram:live"` — a different key than the gateway's `"telegram:6080816249"`. The active draft was stored under one key and looked up under another.

## Fix

Added a `"telegram:live"` → `"telegram:6080816249"` mapping in `source_scope()`. Now all three variants normalize to the same scope key:

```
source_scope("telegram:live")            → telegram:6080816249
source_scope("telegram:6080816249")      → telegram:6080816249
source_scope("telegram:6080816249:...")  → telegram:6080816249
```

This bridges old plugin code (no gateway restart needed) and gateway follow-ups.

## Verification

### Simulated live flow (old plugin + gateway follow-up)
- Create with `source_link="telegram:live"` → draft REP-7E2590C0 created
- Follow-up with `source_link="telegram:6080816249:msg999"` → same row updated, pointer cleared
- All three source_scope variants confirmed equal

### Live draft REP-8BD6B07D
- Updated via explicit `id=REP-8BD6B07D` → status=ready, board-visible
- Exported safely in `approved_reports.json`

### Sync verification
- 10 board-visible reports, 0 private-review
- REP-8BD6B07D exported with "gloves and snacks" summary
- REP-7E2590C0 exported with "gloves and snacks" summary

## Notes
- This also fixes `/need` and `/donation` follow-up tracking since they use the same `"telegram:live"` source_link.
- The fix survives gateway restart — when the new plugin code (with `"telegram:6080816249"`) eventually loads, the scope mapping still works because both `"telegram:live"` and `"telegram:6080816249"` resolve to the same key.
