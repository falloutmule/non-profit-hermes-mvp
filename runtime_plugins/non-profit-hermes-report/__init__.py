"""Deprecated compatibility shim for the historical /report command."""
from __future__ import annotations

from non_profit_hermes import router


def _report(args: str = "") -> str:
    try:
        return router.run_plugin_command("report", args or "")
    except Exception:
        return (
            "Non-Profit Hermes could not run /report. "
            "Please try again or check gateway logs."
        )


def register(ctx) -> None:
    ctx.register_command(
        "report",
        _report,
        description="Non-Profit Hermes: submit a report.",
        args_hint="type=... summary=...",
    )
