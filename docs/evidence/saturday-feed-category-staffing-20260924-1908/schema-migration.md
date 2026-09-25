# Schema migration

VERIFIED production migration3→4; SQLite integrity ok. Stable category definitions, dated defaults, occurrence snapshots and pending SMS context added. Category references and audit columns preserve old rows. One-active-assignment uniqueness preserved. Pending-offer uniqueness now per occurrence/category; generic compatibility retained. Reopen with multiple category offers covered by regression tests.

Pre-upgrade backup: C:\ProgramData\HermesVolunteerBoard\backups\snapshot-2026-09-25T01-22-48-810Z.sqlite
Rollback across schema versions requires matching code/database. Do not restore an old snapshot over newer accepted writes without reconciling authoritative state.
