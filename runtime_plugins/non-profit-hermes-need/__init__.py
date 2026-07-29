"""Deprecated compatibility shim for the historical /need command."""
from __future__ import annotations

from non_profit_hermes import router


def _need(args: str = "") -> str:
    try:
        return router.run_plugin_command("need", args or "")
    except Exception:
        return (
            "Non-Profit Hermes could not run /need. "
            "Please try again or check gateway logs."
        )


def register(ctx) -> None:
    ctx.register_command(
        "need",
        _need,
        description="Non-Profit Hermes: create a safe board-visible need request through the router/backend.",
        args_hint="id=REQ-... description=... urgency=normal needed_by=unknown location=public-safe-test-area privacy_level=board-visible next_action=review",
    )
