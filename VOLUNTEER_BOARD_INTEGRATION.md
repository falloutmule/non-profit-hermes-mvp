# Volunteer Board operator connection

Source: this repository. Dedicated live operator: Hermes profile nonprofit-v1, task Hermes_Gateway_nonprofit_v1. Existing Sheets/Calendar commands remain unchanged. /event board is reserved for the authoritative Volunteer Board HTTP API. Never mutate its SQLite directly.

## Telegram commands

- `/board`: list event ID, date, capacity, status and keyword; no private roster.
- `/board show 1`: inspect Saturday Pantry occurrence1.
- `/board pantry preview`: preview the upcoming 12 Saturdays without writes.
- `/board pantry prepare`: reconcile upcoming12 weekly drafts; duplicates skipped; existing changes/cancellations preserved. No SMS.
- `/board publish 1`: publish one reviewed draft only after the protected real_use_review_complete gate is true. No automated publication.

First Saturday Pantry is September26,2026, 3:45–5:00 PM America/Denver, 302 South Ave, Grand Junction, CO, capacity6. Signup keyword PANTRY20260926. Each occurrence gets PANTRYYYYYMMDD, a separate capacity and standby queue. DST conversion uses IANA America/Denver; November dates correctly shift UTC while local time stays fixed.

HermesVolunteerBoard-PantryDrafts runs Mondays06:00 local Windows time as the operator with S4U (no interactive login), StartWhenAvailable and IgnoreNew. It calls scripts/volunteer_board_operator.py pantry prepare through loopback API and materializes a rolling12-week horizon of drafts. It never publishes or sends SMS. The Board event records remain authoritative. To stop recurrence replenishment, disable this task; do not delete existing events. Task result nonzero means reconcile Board records before retrying.

## Runtime and recovery

The dedicated profile is C:\Users\fallo\AppData\Local\hermes\profiles\nonprofit-v1. Its unified plugin differs from the older shared-home plugins. Canonical adapter overlay: runtime_plugins/nonprofit-v1-board-overlay/commands.py; deployed as profile plugins/non-profit-hermes/commands.py. Only event args beginning with board are intercepted; other commands delegate to the existing package router. The adapter loads the repository connector at each invocation. Earlier canonical legacy router also supports the same route; no Sheets/Calendar calls occur for Board commands.

Credential: protected profile private/configuration/volunteer-board.json containing base_url, admin_token and real_use_review_complete. Never commit/copy it into public evidence. It has no Twilio credentials. User/Admin/SYSTEM ACL only. The connector refuses redirects and requires loopback127.0.0.1:8787. For later laptop migration update the destination-validation model deliberately; do not send bearer credentials to arbitrary URLs.

Runtime restart uses the dedicated profile CLI `hermes --profile nonprofit-v1 gateway stop` followed by existing task Hermes_Gateway_nonprofit_v1. Stop-ScheduledTask alone can leave child processes running. Never restart the shared/main gateway or use --all. A backup of pre-integration commands.py is retained under profile private/board-integration-backup-*.

## Invitation gate

Public/application text is updated to volunteer coordination, policy version2026-09-23. Historical consent rows and opted-out status are unchanged. Confirm live Pages/app wording and review the existing approved Twilio campaign against real use manually before setting real_use_review_complete true locally. No Twilio campaign mutation is performed by this integration. Publish reviewed drafts only after that check; volunteers opt in themselves. No contacts imported, SMS sent or volunteers invited during setup.

## Verification boundary

Connector unit tests cover DST, recurrence, repeat preparation, drift protection, publication hold and secret redaction. Live adapter invocation through installed profile tested locally; a human-originated Telegram command is still required to establish end-to-end Telegram transport. No claim that real SMS delivery through Funnel was tested here.

## September23 command-registration repair

The direct adapter import check was insufficient: the pinned gateway's CLI startup path did not retain /event in its live registry. scripts/nonprofit_gateway_entry.py pins HERMES_HOME to nonprofit-v1, discovers/verifies the registry and calls the pinned gateway.run entry point directly. It verifies registration again eight seconds into the running gateway. Live output confirms NONPROFIT_EVENT_REGISTRY_LIVE=True with the correct profile. scripts/windows/Start-NonprofitV1.ps1 preserves the existing private-binding loader and launches this bootstrap with the dedicated Python runtime. No shared gateway/runtime source was modified. Prior launcher retained in the profile private directory for rollback.

Regression check: run the dedicated Python with scripts/nonprofit_gateway_entry.py --check-registry; verify it lists Board events. After startup, check the live-registry marker and Telegram polling connection. Human Telegram response is still the end-to-end confirmation; local handler tests alone are not enough.

## Concise Telegram display

/board shows shared schedule/location once and three dates per page. Use /board 2 for more dates. /board show <id> presents one readable event card with status and signup keyword. No changes to events, capacity, publication, consent or messaging behavior. The adapter loads presentation changes at invocation, so no gateway restart is required.

## Direct Telegram menu command

In @HnonProfitBOT, open Menu and select /board (Volunteer dates and event details). No arguments are needed. /board 2 shows the next three dates; /board show 1 opens one event. Legacy /event board commands remain supported. The default Telegram command menu preserves existing commands until the operator identifies the five to retain. Post-connect menu mutations remain disabled so runtime startup does not replace this menu.

The bootstrap now verifies NONPROFIT_BOARD_REGISTRY_LIVE=True. Telegram schedule responses were confirmed by the operator before this shortcut change. To restart the dedicated gateway, stop its scheduled task and verify/stop only any remaining child listening on 8643 whose command line contains nonprofit_gateway_entry.py, then start Hermes_Gateway_nonprofit_v1. Never stop the shared Hermes gateway.
