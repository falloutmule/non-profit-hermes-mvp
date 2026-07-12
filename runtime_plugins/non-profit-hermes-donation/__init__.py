from __future__ import annotations

import sys
import traceback
from pathlib import Path

REPO = Path(r"C:\Users\fallo\non-profit-hermes-mvp")
SCRIPTS = REPO / "scripts"


def _donation(args: str = "") -> str:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    try:
        import telegram_intake_router
        result = telegram_intake_router.handle_message("/donation " + args.strip(), source_link="telegram:live")
        return telegram_intake_router._result_to_text(result)
    except Exception as exc:
        return "Donation command failed. Check gateway logs. Error: " + str(exc) + "\n" + traceback.format_exc(limit=1)


def register(ctx):
    ctx.register_command(
        "donation",
        _donation,
        description="Non-Profit Hermes: create a safe donation draft through the router/backend.",
        args_hint="id=DON-... item=... quantity=... pickup_or_dropoff=... location=... available_date=... receipt_needed=... consent_to_public_thanks=... next_action=review",
    )
