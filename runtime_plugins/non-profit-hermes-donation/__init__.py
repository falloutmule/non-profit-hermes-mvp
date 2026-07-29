"""Deprecated compatibility shim for the historical /donation command."""
from __future__ import annotations

from non_profit_hermes import router


def _donation(args: str = "") -> str:
    try:
        return router.run_plugin_command("donation", args or "")
    except Exception:
        return (
            "Non-Profit Hermes could not run /donation. "
            "Please try again or check gateway logs."
        )


def register(ctx) -> None:
    ctx.register_command(
        "donation",
        _donation,
        description="Non-Profit Hermes: create a safe donation draft through the router/backend.",
        args_hint="id=DON-... item=... quantity=... pickup_or_dropoff=... location=... available_date=... receipt_needed=... consent_to_public_thanks=... next_action=review",
    )
