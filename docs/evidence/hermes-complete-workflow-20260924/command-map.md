# Command map — pre-integration baseline

Runtime implementation inspected in installed non_profit_hermes.router, operations and models. Classifications describe code, not production write execution.

| Command | Implementation | Bare command before repair | Existing responsibility |
|---|---|---|---|
| daily | IMPLEMENTED; integration PARTIAL | read-only in-memory approved-safe summary | Google Requests, Donations, Reports, CalendarLog, AuditLog; staffing/inventory placeholders |
| need | IMPLEMENTED | routes intake, not guaranteed read-only | Requests draft/create/update, active follow-up, privacy hold, audit |
| donation | IMPLEMENTED | routes intake, not guaranteed read-only | Donations drafts/follow-up; listing/thanks consent distinct |
| report | IMPLEMENTED | routes intake, not guaranteed read-only | Reports drafts/follow-up, approved summary/privacy |
| task | IMPLEMENTED | routes intake, not guaranteed read-only | Tasks draft/follow-up and audit |
| inventory | IMPLEMENTED | routes intake, not guaranteed read-only | Inventory create/update/follow-up and audit |
| event | PARTIAL for unified design | routes old intake, not guaranteed read-only | Sheet EventDraft in CalendarLog; exact one-shot local Calendar promotion; overlay legacy event board routes API |
| board | IMPLEMENTED; new design PARTIAL | read-only list | authenticated Board adapter; prior event-write responsibilities need move to event |

run_plugin_command uses source_link telegram:live and forwards to handle_message. Do not invoke bare legacy intake for verification: it reaches services and handlers that can create draft/audit rows. Read-only help wrapper required.

Natural language: package handle_message accepts follow-up text and resolves active drafts in event/report/task/inventory/donation/need order; primary creation is command-structured. Profile skill tells Hermes privacy/approval rules and uses operator script for Board. No independently verified generic natural-language live tool invocation is claimed here.

Menu baseline intentionally only board,new,usage,status,model,stop. Restoration must verify actual applicable Telegram scopes and startup persistence, not just COMMANDS metadata.
