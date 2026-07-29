"""Deprecated compatibility shim for the historical /daily command."""
from __future__ import annotations

from non_profit_hermes import router


def _daily(args: str = "") -> str:
    try:
        return router.run_plugin_command("daily", args or "")
    except Exception:
        return (
            "Non-Profit Hermes could not run /daily. "
            "Please try again or check gateway logs."
        )


def register(ctx) -> None:
    ctx.register_command(
        "daily",
        _daily,
        description="Non-Profit Hermes board-safe daily summary",
        args_hint="",
    )
