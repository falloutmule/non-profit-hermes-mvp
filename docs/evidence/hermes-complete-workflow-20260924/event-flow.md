# Event workflow

VERIFIED /event uses Board event operations, optional staffing/standby/completion, explicit draft default. Stored recurrence drives future materialization. One/future recurring edits are explicit. Existing legacy CalendarLog mapping remains readable; Board IDs map deterministically to Calendar IDs. Drafts never create Calendar entries. Calendar write/failure/retry paths use isolated fixtures, live Calendar reads passed.

DONE records first eligible confirmed volunteer completion of the entire reportable event; multiple/retry ambiguity requires explicit keyword. No free-text report retention. Three Board review fixes tested before deploy.
