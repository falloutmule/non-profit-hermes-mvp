# Google workflows — baseline inventory

VERIFIED code: installed package operations uses existing Sheets and Calendar services; configured IDs remain private runtime configuration. Schema tabs: Requests, Donations, Reports, Tasks, Inventory, CalendarLog, AuditLog. Additional historical tabs require live schema inspection, not assumption.

Requests contains consent/privacy, public/private location, assignment/status, NextAction and source-link fields. Donations separates donor contact, listing permission, thanks consent, privacy and public-safe data. Reports separates SensitiveDetails, PublicSummaryDraft, PublicSummaryAllowed and privacy. Tasks are internal records and lack a general privacy field. Inventory has storage location, PublicNeedAllowed and notes. CalendarLog holds EventDraftID, CalendarEventID, public-safe fields, privacy and approval status. AuditLog has before/after and source links; those raw fields must never be mirrored wholesale.

Private legacy operations write the proper tab and AuditLog. Calendar draft promotion has explicit one-shot local authorization, confirmation, completeness/privacy guards and idempotent Calendar ID mapping. Preserve historical records; route all new events to Board.

Credential startup path is a symlink to the canonical existing token. No OAuth flow started. Authenticated API checks and workbook sharing inspection are performed by the main integration run; this inventory does not claim them from installed libraries or previous reports.

Read-only daily currently uses an approved-safe in-memory snapshot; no public-file generation. Inventory and volunteer staffing sections are placeholders. New member workbook must use field allowlists and existing public-safe eligibility, not expose raw AuditLog Before/After, contact fields, source links or notes. Internal Tasks need explicit safe field selection and member visibility policy.

Existing scripts/non_profit_hermes_ops.py is historical source, not the runtime package import. Profile skill has operator workflow guidance; existing real Docs/Drive capabilities are separately verified by main integration rather than inferred from package dependencies. No dummy Docs needed.
