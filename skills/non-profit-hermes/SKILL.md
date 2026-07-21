---
name: non-profit-hermes
description: Use when operating the seven-command Non-Profit Hermes workflow. Keeps intake draft-first, privacy-classified, approval-gated, and auditable.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [nonprofit, telegram, privacy, approvals, audit]
    related_skills: []
---

# Non-Profit Hermes Operations

## Overview

Use the seven commands as a small, predictable nonprofit operations interface. Keep intake draft-first, collect only necessary facts, preserve the private/public boundary, and verify each result before reporting success.

The workflow does not infer authorization from configuration or availability. A working integration permits an action only after the action's own privacy and approval conditions are satisfied.

## When to Use

Use this skill for:

- board-safe daily summaries;
- nonprofit request, donation, report, task, and inventory intake;
- event drafts and separately authorized Calendar promotion;
- approval-controlled public-safe drafts.

Do not use it for automatic publication, broad Calendar authorization, payment processing, or exposing sensitive case details.

## Privacy Gate

Classify each fact before using it:

- `private` for identifying, contact, exact-location, personal, or otherwise sensitive information;
- `internal` for staff operations that must not be public;
- `board-visible` for reviewed board material;
- `public-safe` for minimized, non-identifying material eligible for an approval-gated public draft.

When uncertain, choose the more restrictive class. Do not invent missing information. Mark it `unknown` or ask one focused follow-up question.

## Command Workflow

### `/daily`

1. Read only approved-safe source data.
2. Summarize urgent items, dated commitments, resource gaps, pending approvals, and due follow-ups.
3. Keep private details out of the response.
4. Confirm the path performed no Google write, public-file generation, publication, or durable credential refresh.

Completion criterion: the summary is board-safe and the operation is verified read-only.

### `/need`

1. Capture the need, urgency, needed-by date, safe contact route, privacy level, and next action when provided.
2. Create or update a draft; do not infer a sensitive location or missing consent.
3. Ask only for facts required to move the draft forward.
4. Verify the resulting record and audit entry.

Completion criterion: the draft exists with unknowns and privacy state explicit.

### `/donation`

1. Capture the offered item, quantity, handoff method, availability, privacy state, and next action.
2. Keep public listing and public thanks as separate consent decisions.
3. Leave incomplete intake in draft or needs-review state.
4. Verify the resulting record and audit entry.

Completion criterion: the donation draft is traceable and no public consent was assumed.

### `/report`

1. Capture a concise activity summary, date, operational counts, follow-up needs, privacy level, and next action.
2. Keep sensitive notes out of any public summary.
3. Populate public-safe summary material only when policy and approval state permit it.
4. Verify the resulting record and audit entry.

Completion criterion: the report is classified, auditable, and safe for its stated audience.

### `/task`

1. Capture a clear title, owner if known, due date if known, priority, privacy level, and next action.
2. Keep tasks internal.
3. Do not turn a vague date into a Calendar event.
4. Verify the resulting record and audit entry.

Completion criterion: the task is actionable or its missing fields are explicitly listed.

### `/inventory`

1. Capture item, quantity, unit, category, threshold if known, condition, and next action.
2. Use the stable item identifier when updating an existing record.
3. Keep storage details private or internal.
4. Verify the resulting record and audit entry.

Completion criterion: the inventory record reflects the intended item and quantity without public exposure.

### `/event`

1. Create a Sheet-only event draft with title, date/time, duration, and privacy-safe location information when available.
2. Treat incomplete timing as a draft or task, not a Calendar event.
3. Require fresh authorization for the exact event before promotion.
4. Use only the guarded one-shot promotion path; prior approval or configuration never grants continuing authority.
5. Verify the same-row Calendar identifier and audit evidence after an authorized promotion.

Completion criterion: either a safe draft exists, or the exact authorized one-shot promotion is verified once.

## Publication Boundary

Public-safe classification is not publication approval. Before any public action:

1. minimize the content to non-identifying facts;
2. tie the draft to approved-safe source records;
3. request approval for the exact text and destination;
4. publish only after that approval;
5. verify the exact released artifact and audit trail.

If wording changes after approval, return it to review.

## Common Pitfalls

1. Treating command availability as permission. Availability proves only that a handler exists; action-specific authorization is still required.
2. Treating `public-safe` as `approved`. It means eligible for review, not cleared for release.
3. Creating Calendar events from vague dates. Keep them as tasks or drafts until date, time, and exact authorization are present.
4. Reporting a mutation from a successful function return alone. Read back the intended record and confirm its audit evidence.
5. Reusing sensitive details in summaries. Minimize again at every audience boundary.

## Completion Checks

Before replying that work succeeded, confirm:

- [ ] the correct command and target record were used;
- [ ] missing facts remain unknown or were requested;
- [ ] privacy classification matches the content;
- [ ] every mutation has audit evidence;
- [ ] `/daily` remained read-only;
- [ ] Calendar promotion had exact one-shot authorization;
- [ ] publication had approval for the exact content;
- [ ] the final response separates completed, failed, and pending work.
