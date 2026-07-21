"""Portable, side-effect-free configuration resolution.

Callers may inject an environment mapping and home directory for deterministic tests.
No credentials or production integration identifiers are selected by default.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


ENV_CONFIG_DIR = "NON_PROFIT_HERMES_CONFIG_DIR"
ENV_DATA_DIR = "NON_PROFIT_HERMES_DATA_DIR"
ENV_STATE_DIR = "NON_PROFIT_HERMES_STATE_DIR"
ENV_PUBLIC_DIR = "NON_PROFIT_HERMES_PUBLIC_DIR"
ENV_CREDENTIALS_FILE = "NON_PROFIT_HERMES_CREDENTIALS_FILE"
ENV_SPREADSHEET_ID = "NON_PROFIT_HERMES_SPREADSHEET_ID"
ENV_CALENDAR_ID = "NON_PROFIT_HERMES_CALENDAR_ID"
ENVIRONMENT_NAMES = (
    ENV_CONFIG_DIR,
    ENV_DATA_DIR,
    ENV_STATE_DIR,
    ENV_PUBLIC_DIR,
    ENV_CREDENTIALS_FILE,
    ENV_SPREADSHEET_ID,
    ENV_CALENDAR_ID,
)
_UNSET = object()


@dataclass(frozen=True)
class PackageConfig:
    """Resolved local paths and optional external integration identifiers."""

    config_dir: Path
    data_dir: Path
    state_dir: Path
    public_dir: Path
    credentials_file: Path | None = None
    spreadsheet_id: str | None = None
    calendar_id: str | None = None


def resolve_config(
    *,
    config_dir: str | Path | None = None,
    data_dir: str | Path | None = None,
    state_dir: str | Path | None = None,
    public_dir: str | Path | None = None,
    credentials_file: str | Path | None | object = _UNSET,
    spreadsheet_id: str | None | object = _UNSET,
    calendar_id: str | None | object = _UNSET,
    environ: Mapping[str, str] | None = None,
    home: str | Path | None = None,
) -> PackageConfig:
    """Resolve arguments, then documented environment names, then safe defaults."""

    environment = os.environ if environ is None else environ
    resolved_home = Path.home() if home is None else Path(home).expanduser()
    app_name = "non-profit-hermes"
    default_config_dir = resolved_home / ".config" / app_name
    default_data_dir = resolved_home / ".local" / "share" / app_name
    default_state_dir = resolved_home / ".local" / "state" / app_name
    resolved_data_dir = Path(data_dir or environment.get(ENV_DATA_DIR) or default_data_dir).expanduser()
    default_public_dir = resolved_data_dir / "public"
    resolved_credentials = (
        environment.get(ENV_CREDENTIALS_FILE) or None
        if credentials_file is _UNSET
        else credentials_file
    )
    resolved_spreadsheet_id = (
        environment.get(ENV_SPREADSHEET_ID) or None
        if spreadsheet_id is _UNSET
        else spreadsheet_id
    )
    resolved_calendar_id = (
        environment.get(ENV_CALENDAR_ID) or None
        if calendar_id is _UNSET
        else calendar_id
    )
    return PackageConfig(
        config_dir=Path(config_dir or environment.get(ENV_CONFIG_DIR) or default_config_dir).expanduser(),
        data_dir=resolved_data_dir,
        state_dir=Path(state_dir or environment.get(ENV_STATE_DIR) or default_state_dir).expanduser(),
        public_dir=Path(public_dir or environment.get(ENV_PUBLIC_DIR) or default_public_dir).expanduser(),
        credentials_file=(
            Path(resolved_credentials).expanduser()
            if isinstance(resolved_credentials, (str, Path)) and resolved_credentials
            else None
        ),
        spreadsheet_id=(resolved_spreadsheet_id or None) if isinstance(resolved_spreadsheet_id, str) else None,
        calendar_id=(resolved_calendar_id or None) if isinstance(resolved_calendar_id, str) else None,
    )


__all__ = ["ENVIRONMENT_NAMES", "PackageConfig", "resolve_config"]
