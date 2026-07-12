from __future__ import annotations
import sys, traceback
from pathlib import Path

REPO = Path(r"C:\Users\fallo\non-profit-hermes-mvp")
SCRIPTS = REPO / "scripts"

def _report(args: str = "") -> str:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    try:
        import telegram_intake_router
        result = telegram_intake_router.handle_message("/report " + args.strip(), source_link="telegram:6080816249")
        return telegram_intake_router._result_to_text(result)
    except Exception as exc:
        return "Command failed. Check gateway logs. Error: " + str(exc) + "\n" + traceback.format_exc(limit=1)

def register(ctx):
    ctx.register_command("report", _report, description="Non-Profit Hermes: submit a report.",
                         args_hint="type=... summary=...")
