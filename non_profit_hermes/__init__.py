"""Portable foundations for Non-Profit Hermes."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

_DISTRIBUTION_NAME = "non-profit-hermes"
_FALLBACK_VERSION = "1.0.0"

try:
    __version__ = version(_DISTRIBUTION_NAME)
except PackageNotFoundError:
    __version__ = _FALLBACK_VERSION

__all__ = ["__version__"]
