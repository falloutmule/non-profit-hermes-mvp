from __future__ import annotations

import importlib
import sys
from pathlib import Path

REPO = Path(r"C:\Users\fallo\non-profit-hermes-mvp")
SCRIPTS = REPO / "scripts"


def _daily(_raw_args: str = "") -> str:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    try:
        # Force a fresh load of the on-disk router so the live gateway never
        # serves a stale sys.modules copy after edits. This makes /daily always
        # reflect the current scripts/telegram_intake_router.py without requiring
        # a gateway restart.
        sys.modules.pop("telegram_intake_router", None)
        telegram_intake_router = importlib.import_module("telegram_intake_router")
        return telegram_intake_router.run_daily_summary()
    except Exception as exc:
        return "Daily summary failed. Check gateway logs and router script. Error: " + str(exc) + "\n" + __import__("traceback").format_exc(limit=1)


def register(ctx):
    ctx.register_command(
        "daily",
        _daily,
        description="Non-Profit Hermes board-safe daily summary",
        args_hint="",
    )
