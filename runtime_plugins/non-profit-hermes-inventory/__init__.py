"""Deprecated compatibility shim for the historical /inventory command."""
from __future__ import annotations

from non_profit_hermes import router


def _inventory(args: str = "") -> str:
    try:
        return router.run_plugin_command("inventory", args or "")
    except Exception:
        return (
            "Non-Profit Hermes could not run /inventory. "
            "Please try again or check gateway logs."
        )


def register(ctx) -> None:
    ctx.register_command(
        "inventory",
        _inventory,
        description="Non-Profit Hermes: track inventory.",
        args_hint="item=... quantity=... unit=...",
    )
