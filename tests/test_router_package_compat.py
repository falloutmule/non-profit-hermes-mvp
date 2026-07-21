"""Package-boundary, configuration, and legacy-wrapper tests for the router."""
from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_PATH = ROOT / "non_profit_hermes" / "router.py"
LEGACY_PATH = ROOT / "scripts" / "telegram_intake_router.py"


EXPECTED_ROUTER_NAMES = (
    "RouterResult",
    "_result_to_text",
    "parse_message",
    "classify_privacy",
    "source_scope",
    "handle_message",
    "route_need",
    "route_donation",
    "route_report",
    "route_task",
    "route_inventory",
    "route_event",
    "run_daily_summary",
    "write_event_calendar_promotion_authorization",
    "route_event_followup",
    "run_test",
    "main",
)


def _load_legacy_wrapper():
    spec = importlib.util.spec_from_file_location("legacy_telegram_intake_router", LEGACY_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_package_owns_the_router_contract() -> None:
    from non_profit_hermes import router

    assert set(EXPECTED_ROUTER_NAMES) <= set(router.__all__)
    assert all(getattr(router, name).__module__ == router.__name__ for name in EXPECTED_ROUTER_NAMES)


def test_package_source_is_portable_and_uses_canonical_boundaries() -> None:
    source = PACKAGE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    imported_modules.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )

    assert "from non_profit_hermes import approved_safe_sync, config, operations as ops" in source
    assert "sys.path" not in source
    assert "subprocess" not in imported_modules
    assert "C:\\Users\\" not in source
    assert "/Users/" not in source
    assert "6080816249" not in source
    assert not any(module == "scripts" or module.startswith("scripts.") for module in imported_modules)


def test_legacy_live_scope_is_resolved_at_call_time_or_injected(monkeypatch) -> None:
    from non_profit_hermes import router

    monkeypatch.delenv("NON_PROFIT_HERMES_TELEGRAM_SOURCE_SCOPE", raising=False)
    assert router.source_scope("telegram:live") == "telegram:live"

    monkeypatch.setenv("NON_PROFIT_HERMES_TELEGRAM_SOURCE_SCOPE", "telegram:configured-chat")
    assert router.source_scope("telegram:live") == "telegram:configured-chat"
    assert (
        router.source_scope(
            "telegram:live",
            telegram_live_scope="telegram:injected-chat",
        )
        == "telegram:injected-chat"
    )


def test_active_draft_state_accepts_an_explicit_path(tmp_path: Path) -> None:
    from non_profit_hermes import router

    state_path = tmp_path / "nested" / "active-drafts.json"
    state = {"telegram:test": {"active_need_request_id": "REQ-TEST-001"}}

    router.save_active_need_state(state, state_path=state_path)

    assert router.load_active_need_state(state_path=state_path) == state


def test_sync_delegates_directly_to_an_injected_package_call() -> None:
    from non_profit_hermes import router

    sentinel = {"status": "offline-sync"}

    assert router.run_sync(sync_runner=lambda: sentinel) is sentinel


def test_legacy_wrapper_reexports_canonical_objects_by_identity() -> None:
    from non_profit_hermes import router

    legacy = _load_legacy_wrapper()

    assert legacy.__all__ == router.__all__
    assert all(getattr(legacy, name) is getattr(router, name) for name in router.__all__)
