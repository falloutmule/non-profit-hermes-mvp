from __future__ import annotations

import sys
import traceback
from pathlib import Path

REPO = Path(r"C:\Users\fallo\non-profit-hermes-mvp")
SCRIPTS = REPO / "scripts"


def _need(args: str = "") -> str:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    try:
        import telegram_intake_router
        result = telegram_intake_router.handle_message("/need " + args.strip(), source_link="telegram:live")
        return telegram_intake_router._result_to_text(result)
    except Exception as exc:
        return "Need command failed. Check gateway logs. Error: " + str(exc) + "\n" + traceback.format_exc(limit=1)


def register(ctx):
    ctx.register_command(
        "need",
        _need,
        description="Non-Profit Hermes: create a safe board-visible need request through the router/backend.",
        args_hint="id=REQ-... description=... urgency=normal needed_by=unknown location=public-safe-test-area privacy_level=board-visible next_action=review",
    )
