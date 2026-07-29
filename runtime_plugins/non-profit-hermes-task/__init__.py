"""Deprecated compatibility shim for the historical /task command."""
from __future__ import annotations

from non_profit_hermes import router


def _task(args: str = "") -> str:
    try:
        return router.run_plugin_command("task", args or "")
    except Exception:
        return (
            "Non-Profit Hermes could not run /task. "
            "Please try again or check gateway logs."
        )


def register(ctx) -> None:
    ctx.register_command(
        "task",
        _task,
        description="Non-Profit Hermes: create a task.",
        args_hint="title=... assigned_to=... due_date=...",
    )
