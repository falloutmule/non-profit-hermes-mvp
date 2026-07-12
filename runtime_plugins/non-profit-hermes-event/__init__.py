from __future__ import annotations

import re
import shlex
import sys
import traceback
from pathlib import Path

REPO = Path(r"C:\Users\fallo\non-profit-hermes-mvp")
SCRIPTS = REPO / "scripts"

# Draft-first live /event command. Calendar creation is disabled by default.
# The only exception is an exact locally authorized one-shot promotion routed through
# the repository guard; this never permanently enables Calendar creation or calls
# Calendar backend create functions directly.

_PROMOTION_ID_FIELDS = {"id", "eventdraftid", "event_draft_id", "eventid", "event_id"}
_PROMOTION_CONFIRMATION_FIELDS = {"create_calendar", "confirm_create"}
_TRUTHY_VALUES = {"1", "true", "yes", "on"}


def _promotion_dispatch(args: str) -> tuple[str, bool]:
    """Return raw follow-up text or reject an unsafe promotion-shaped payload.

    A promotion has no mutable draft fields: it is only an explicit draft ID and
    explicit confirmation. Keeping it raw is required for router follow-up dispatch.
    """
    raw = args.strip()
    try:
        tokens = shlex.split(raw)
    except ValueError:
        return "", False

    fields: list[tuple[str, str]] = []
    free_tokens: list[str] = []
    for token in tokens:
        if "=" in token:
            key, value = token.split("=", 1)
            fields.append((key.strip().lower().replace("-", "_"), value.strip()))
        else:
            free_tokens.append(token)

    populated_ids = [
        (key, value) for key, value in fields
        if key in _PROMOTION_ID_FIELDS and value
    ]
    confirmation_fields = [
        (key, value) for key, value in fields
        if key in _PROMOTION_CONFIRMATION_FIELDS
    ]
    truthy_confirmations = [
        (key, value) for key, value in confirmation_fields
        if value.lower() in _TRUTHY_VALUES
    ]
    has_id_alias = any(key in _PROMOTION_ID_FIELDS for key, _ in fields)
    has_confirmation_alias = bool(confirmation_fields)
    if not has_confirmation_alias:
        # An explicit ID alone is an ordinary draft update, not a promotion.
        return "", False
    if not has_id_alias:
        return "Promotion request rejected: promotion may include only one EVT draft ID and one create confirmation.", True

    draft_id = populated_ids[0][1] if len(populated_ids) == 1 else ""
    if (
        len(populated_ids) != 1
        or len(confirmation_fields) != 1
        or len(truthy_confirmations) != 1
        or not re.fullmatch(r"EVT-[0-9A-F]{8}", draft_id)
        or len(fields) != 2
        or free_tokens
    ):
        return "Promotion request rejected: promotion may include only one EVT draft ID and one create confirmation.", True
    return raw, True


def _event(args: str = "") -> str:
    raw_args = (args or "").strip()
    dispatch_text, is_promotion = _promotion_dispatch(raw_args)
    if is_promotion and dispatch_text.startswith("Promotion request rejected:"):
        return dispatch_text
    if not is_promotion:
        dispatch_text = "/event " + raw_args
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    try:
        # Force a fresh load of the on-disk router so the live gateway never
        # serves a stale sys.modules copy after edits (no restart required).
        sys.modules.pop("telegram_intake_router", None)
        import telegram_intake_router
        result = telegram_intake_router.handle_message(
            dispatch_text,
            source_link="telegram:6080816249",
            allow_calendar_creation=False,
            calendar_promotion_mode="one-shot-local-authorization",
        )
        return telegram_intake_router._result_to_text(result)
    except Exception as exc:
        return "Event command failed. Check gateway logs. Error: " + str(exc) + "\n" + traceback.format_exc(limit=1)


def register(ctx):
    ctx.register_command("event", _event,
        description="Non-Profit Hermes: draft-first /event — writes a Sheet-only EventDraft; exact locally authorized one-shot promotion is the only exception, with no permanent Calendar enablement.",
        args_hint='event_title="Safe test event" start=2099-01-01T09:00:00-06:00 end=2099-01-01T10:00:00-06:00 type=meeting location="safe venue"',
    )
