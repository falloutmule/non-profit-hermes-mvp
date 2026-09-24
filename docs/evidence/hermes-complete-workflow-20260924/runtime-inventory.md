# Runtime inventory — baseline before integration

Inspected 2026-09-24; read-only inventory, not final acceptance.

VERIFIED: Hermes_Gateway_nonprofit_v1 is Running, identity fallo. Action launches the dedicated profile startup/Start-NonprofitV1.ps1 with -Port 8643 -EnableTelegram -EnableGoogle. HERMES_HOME points to the nonprofit-v1 profile; shared agent is outside scope.

Actual Python and imported package are the pinned venv under AppData/Local/hermes/staging/non-profit-hermes-v1/20260804T170601Z/telegram-canary-remediation-20260805T100000Z/venv-telegram-fresh. Actual router is Lib/site-packages/non_profit_hermes/router.py, not the repository worktree copy.

Installed router SHA256: 362A39AAE08AB4ED7E50D5277AB448DC08398C40FFEAEDF1E2800388415A0DCB.
Repository worktrees/nph-v1-package-001/non_profit_hermes/router.py SHA256: 838C8621C6BD2F27D7ACA6C5B86D94FC12A6B665D3D30B5D450A4205D28CD6CB.
They differ. Do not replace installed behavior from the historical worktree without comparison.

Active overlay delegates nonprofit commands to installed router; Board dispatch dynamically loads repository scripts/volunteer_board_operator.py. Bootstrap discovers the plugin registry and calls gateway.run.main directly. Installed profile skill has established privacy/approval/draft-first rules and operator addendum; several event-only Google assumptions require revision.

Google credential path in startup is private/google/google_token.json. VERIFIED SymbolicLink resolves to C:/Users/fallo/AppData/Local/hermes/google_token.json; the apparent different path is not a second credential.

No runtime configuration, credentials, task, or source changed by this inventory.
