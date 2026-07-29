"""Compatibility and CLI wrapper for :mod:`non_profit_hermes.router`."""
from __future__ import annotations

from non_profit_hermes.router import *  # noqa: F401,F403
from non_profit_hermes.router import __all__, main


if __name__ == "__main__":
    raise SystemExit(main())
