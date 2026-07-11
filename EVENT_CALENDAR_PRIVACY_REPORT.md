# EVENT-001 Calendar Publication Privacy Gate Report

## Risk addressed

Calendar publication treats `CalendarLog` as the sole content authority. Google Calendar is used only to confirm that an exact logged event ID exists and is not cancelled; raw Google event title, description, location, attendees, or other content is not exported.

## CalendarLog schema and creation guard

`CalendarLog` has 24 fields. The backend and sync definitions match exactly, with these appended fields retained in this order:

```text
EventDraftID, PrivacyLevel, PublicCalendarAllowed, PublicTitle,
PublicDescription, PublicLocation, ApprovalStatus, SourceMessageLink, Notes
```

Immediately before `create_calendar_event()` appends its `CalendarLog` row, it now calls:

```python
ensure_header(svc_sheets, "CalendarLog")
```

This is a schema guard only; it does not change Calendar event creation behavior.

## Export allowlist and gate

A `CalendarLog` row exports only when all conditions hold:

- `CalendarEventID` is nonempty;
- `PrivacyLevel` is `board-visible`, `public-safe`, or `board-visible-test`;
- `PublicCalendarAllowed` is `yes`, `true`, or `1` (case-insensitive);
- `ApprovalStatus` is `approved` or `created`;
- `Status` is `confirmed` or `ready`;
- `PublicTitle` is nonempty; and
- the exact `CalendarEventID` exists in the complete paginated live-ID/status lookup and is not `cancelled`.

`safe_calendar_export()` follows `nextPageToken` until exhausted. It exports exactly these eight CalendarLog-derived fields:

```text
CalendarEventID, EventTitle, EventType, StartDateTime, EndDateTime,
Description, Location, Status
```

`EventTitle`, `Description`, and `Location` come exclusively from `PublicTitle`, `PublicDescription`, and `PublicLocation`; no raw Google Calendar content is used in output.

## Strict TDD evidence and focused local results

New test cases were written before the two production repairs. The initial test import exposed a test-only dynamic-module registration issue caused by the router's dataclass; the loader was corrected by registering the imported module in `sys.modules`. The behavior RED run then produced the expected failures before production changes:

```text
python -m unittest discover -s tests -p 'test_event_calendar_privacy.py' -v
FAILED (errors=2)
```

The failures were expected: the page-two exact-ID event was absent because pagination was missing, and no `CalendarLog` header update existed before the append.

After the minimal production repairs, the GREEN run was:

```text
python -m unittest discover -s tests -p 'test_event_calendar_privacy.py' -v
Ran 8 tests in 0.001s
OK
```

The local fake-only suite covers:

- matching 24-field backend/sync schemas;
- private sentinel exclusion and safe-only output;
- mandated fixture values: `Community pantry test`, `Approved-safe event description`, and `Public service area`;
- a qualified exact ID found only on Calendar list page two;
- stale/cancelled IDs and table-driven denial for an empty ID, invalid public flag, invalid approval, invalid status, and empty public title;
- fake-Sheets proof that the `CalendarLog` header update precedes its append; and
- `/daily` compatibility with the eight-field export, safe title/status rendering, sync marker/version rendering, and duplicate-title suppression, without router changes.

## Parent-performed live status (not produced by this repair)

The parent already performed live schema expansion and live sync verification. The actual live `CalendarLog` header matches all 24 fields, the sync returned `approved_calendar=0`, and `/daily` rendered. This repair did not call Google APIs, modify generated docs, create or change Calendar events, restart the gateway, or modify the router.

There is no live public-event proof in this report: an `approved_calendar=0` sync result does not establish that any live public event exists or was exported.

## Parent-performed generated-file review and privacy searches

The parent-run live sync succeeded with marker `CLEAN_DOCS_DEPLOY_NON_PROFIT_HERMES_002` and these counts:

```text
approved_needs=9
approved_calendar=0
approved_reports=11
approved_donations=6
approved_volunteer_gaps=0
approved_board_log=81
```

The sync produced only timestamp diffs in `docs/deployment-proof.html`, `docs/deployment-proof/index.html`, `docs/index.html`, and `docs/index/index.html`. The parent inspected and restored all four files; no docs files remain modified or will be committed. There was no diff in `approved_needs.json`, `approved_reports.json`, `approved_donations.json`, or `approved_calendar.json`. After restoration, the marker was present in 13 current generated docs files.

Exact searches across docs returned `NO MATCH` for:

```text
PRIVATE-EVENT-LEAK-TEST-7F21
PrivateLocation
SourceMessageLink
telegram:6080816249
Safeway
medical
addiction
legal
camp
family crisis
```

The term `pantry` matched only pre-existing approved report content in `docs/data/approved_reports.json` at lines 45, 46, 50, 55, 56, 60, 65, 66, 70, 75, 76, 80, 85, 86, 90, 95, and 105. These matches were not Calendar or inventory output, and `approved_reports.json` was unchanged by EVENT-001.

The inventory-detail label search for `StorageLocation`, `QuantityOnHand`, `ItemName`, `MinimumNeeded`, `Condition`, `NeededThisWeek`, and `PublicNeedAllowed` returned `NO MATCH`. The broader term `Notes` matched only the sentence `Did NOT export SensitiveNotes...` in `docs/DOCS_SYNC_UPDATE_REPORT.md`, not data.

## Final local verification required for this repair

```text
python -m unittest discover -s tests -p 'test_event_calendar_privacy.py' -v
python -m py_compile scripts/non_profit_hermes_ops.py scripts/sync_approved_safe_data.py tests/test_event_calendar_privacy.py
git diff --check
```
