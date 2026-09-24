"""Organization-facing commands; one dispatcher for Telegram and natural language."""
from typing import NamedTuple
import importlib.util
from pathlib import Path
class CommandSpec(NamedTuple):
    name: str
    description: str
    args_hint: str
COMMANDS = tuple(CommandSpec(name, description, "[request]") for name, description in (
    ("daily", "Organization briefing"),
    ("need", "Needs and priorities"),
    ("donation", "Record and inspect donations"),
    ("report", "Organizational reports"),
    ("task", "Internal tasks and follow-ups"),
    ("inventory", "Supplies and inventory"),
    ("event", "Create and manage events"),
    ("board", "Staffing, openings and standby"),
))
def make_handler(command_name):
    def handler(raw_args=""):
        try:
            source = Path(r"C:\Users\fallo\non-profit-hermes-mvp\scripts\nonprofit_workflow.py")
            spec = importlib.util.spec_from_file_location("nonprofit_workflow", source)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module.dispatch(command_name, raw_args or "")
        except Exception:
            return "Non-Profit operation unavailable. Check service status; do not retry writes blindly."
    return handler
