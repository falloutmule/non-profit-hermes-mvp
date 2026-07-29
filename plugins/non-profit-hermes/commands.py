"""Canonical Non-Profit Hermes command metadata and thin handlers."""
from __future__ import annotations

from typing import NamedTuple

from non_profit_hermes import router


class CommandSpec(NamedTuple):
    name: str
    description: str
    args_hint: str


COMMANDS = (
    CommandSpec(
        "daily",
        "Non-Profit Hermes board-safe daily summary",
        "",
    ),
    CommandSpec(
        "need",
        "Non-Profit Hermes: create a safe board-visible need request through the router/backend.",
        "id=REQ-... description=... urgency=normal needed_by=unknown location=public-safe-test-area privacy_level=board-visible next_action=review",
    ),
    CommandSpec(
        "donation",
        "Non-Profit Hermes: create a safe donation draft through the router/backend.",
        "id=DON-... item=... quantity=... pickup_or_dropoff=... location=... available_date=... receipt_needed=... consent_to_public_thanks=... next_action=review",
    ),
    CommandSpec(
        "report",
        "Non-Profit Hermes: submit a report.",
        "type=... summary=...",
    ),
    CommandSpec(
        "task",
        "Non-Profit Hermes: create a task.",
        "title=... assigned_to=... due_date=...",
    ),
    CommandSpec(
        "inventory",
        "Non-Profit Hermes: track inventory.",
        "item=... quantity=... unit=...",
    ),
    CommandSpec(
        "event",
        "Non-Profit Hermes: draft-first /event — writes a Sheet-only EventDraft; exact locally authorized one-shot promotion is the only exception, with no permanent Calendar enablement.",
        'event_title="Safe test event" start=2099-01-01T09:00:00-06:00 end=2099-01-01T10:00:00-06:00 type=meeting location="safe venue"',
    ),
)


def make_handler(command_name: str):
    """Return a redacting adapter for one package-owned command boundary."""

    def handler(raw_args: str = "") -> str:
        try:
            return router.run_plugin_command(command_name, raw_args or "")
        except Exception:
            return (
                f"Non-Profit Hermes could not run /{command_name}. "
                "Please try again or check gateway logs."
            )

    return handler
