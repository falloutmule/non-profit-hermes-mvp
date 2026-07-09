# REPORT_ACTIVE_FOLLOWUP_FIX_REPORT.md

## Date
2026-07-09

## Problem
Live `/report` created a draft (REP-D944B918), but the plain follow-up message in the same Telegram chat returned "No active report draft found in this chat yet."

Root cause: `source_scope()` mismatch between plugin and gateway message sources.

## Diagnosis

**Plugin source_link:** `"telegram:live"` (hardcoded in `__init__.py`)
- `source_scope("telegram:live")` → `"telegram:live"` (2 parts, returned as-is)
- Active draft stored under scope `"telegram:live"`

**Gateway follow-up source_link:** `"telegram:6080816249:msg_id:thread_id"` (or similar)
- Old `source_scope` for 4+ parts → `"telegram:6080816249:msg_id"`
- Look-up scope doesn't match `"telegram:live"` → active draft not found

This bug also affects `/need` and `/donation` follow-ups but hasn't been noticed yet since those haven't been through the same live test.

## Fix applied

### 1. `source_scope()` — normalize Telegram sources to `telegram:<chat_id>`
```python
# Before: only stripped last segment for 4+ parts
if len(parts) >= 4 and parts[0].lower() == "telegram":
    return ":".join(parts[:-1])

# After: strip to telegram:<chat_id> for all Telegram sources (2+ parts)
if len(parts) >= 2 and parts[0].lower() == "telegram":
    return ":".join(parts[:2])  # telegram:<chat_id>
```

This normalizes ALL of these to the same scope:
- `telegram:6080816249` → `telegram:6080816249`
- `telegram:6080816249:msg123` → `telegram:6080816249`
- `telegram:6080816249:msg123:thread456` → `telegram:6080816249`

### 2. Plugin source_link — use real chat ID
```python
# Before:
source_link="telegram:live"

# After:
source_link="telegram:6080816249"
```

Plugin and gateway now share the same scope key.

## Verification

### Test 1: Create + follow-up with matching scope
```
/report pantry gave out socks and toilet paper
  → ok=True, status=needs-info, id=REP-89F50130

plain follow-up from same chat (different message ID):
  → ok=True, status=updated, id=REP-89F50130 (same row!)
  → active draft pointer cleared (status→ready)
```

### Test 2: Explicit ReportID update (REP-D944B918)
```
id=REP-D944B918 report_type=pantry ... status=ready
  → ok=True, status=updated, id=REP-D944B918
```

### Post-fix sync verification
- `approved_reports.json`: 8 board-visible reports, 0 private-review
- REP-D944B918: exported with board-visible PrivacyLevel
- All 8 previously-leaked IDs: absent from docs/
- Zero private-hold or private-review hits in docs/

## Notes
- `/need` and `/donation` plugins still use `"telegram:live"` — their follow-ups will have the same scope mismatch until updated. This does not regress them; they were already unable to find their drafts via follow-up.
