"""Deprecated compatibility shim for the historical /event command."""
from __future__ import annotations

from non_profit_hermes import router


def _event(args: str = "") -> str:
    try:
        return router.run_plugin_command("event", args or "")
    except Exception:
        return (
            "Non-Profit Hermes could not run /event. "
            "Please try again or check gateway logs."
        )


def register(ctx) -> None:
    ctx.register_command(
        "event",
        _event,
        description="Non-Profit Hermes: draft-first /event — writes a Sheet-only EventDraft; exact locally authorized one-shot promotion is the only exception, with no permanent Calendar enablement.",
        args_hint='event_title="Safe test event" start=2099-01-01T09:00:00-06:00 end=2099-01-01T10:00:00-06:00 type=meeting location="safe venue"',
    )
