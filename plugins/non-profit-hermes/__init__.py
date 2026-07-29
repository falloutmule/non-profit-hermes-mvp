"""Canonical Non-Profit Hermes plugin registration."""
from __future__ import annotations

from .commands import COMMANDS, make_handler


_REGISTRATION_MARKER = "_non_profit_hermes_v1_commands_registered"


def register(ctx) -> None:
    """Register the seven canonical commands once for this plugin context."""
    if getattr(ctx, _REGISTRATION_MARKER, False):
        return

    for command in COMMANDS:
        ctx.register_command(
            command.name,
            make_handler(command.name),
            description=command.description,
            args_hint=command.args_hint,
        )

    setattr(ctx, _REGISTRATION_MARKER, True)
