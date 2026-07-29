"""Compatibility entrypoint for :mod:`non_profit_hermes.operations`."""
from __future__ import annotations

from non_profit_hermes.operations import *  # noqa: F401,F403
from non_profit_hermes.operations import __all__, main


if __name__ == "__main__":
    raise SystemExit(main())