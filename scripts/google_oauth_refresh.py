"""Compatibility entrypoint for the packaged atomic OAuth refresh API."""
from __future__ import annotations

try:
    from non_profit_hermes.oauth_refresh import *  # noqa: F401,F403
    from non_profit_hermes.oauth_refresh import __all__
except ModuleNotFoundError as exc:
    if exc.name != "non_profit_hermes":
        raise
    import importlib.util
    import sys
    from pathlib import Path

    _PACKAGE_DIR = Path(__file__).resolve().parents[1] / "non_profit_hermes"
    _SPEC = importlib.util.spec_from_file_location(
        "non_profit_hermes", _PACKAGE_DIR / "__init__.py", submodule_search_locations=[str(_PACKAGE_DIR)]
    )
    if _SPEC is None or _SPEC.loader is None:
        raise ImportError("non_profit_hermes package is unavailable") from exc
    _PACKAGE = importlib.util.module_from_spec(_SPEC)
    sys.modules["non_profit_hermes"] = _PACKAGE
    _SPEC.loader.exec_module(_PACKAGE)
    from non_profit_hermes.oauth_refresh import *  # noqa: F401,F403
    from non_profit_hermes.oauth_refresh import __all__
