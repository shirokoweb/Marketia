"""Persistent user settings stored in ~/.marketia/settings.json."""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger("marketia")

_SETTINGS_DIR = Path.home() / ".marketia"
_SETTINGS_FILE = _SETTINGS_DIR / "settings.json"


def load_settings() -> dict:
    """Load settings from disk, returning an empty dict if the file is absent or corrupt."""
    if not _SETTINGS_FILE.exists():
        return {}
    try:
        return json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("Could not read settings from %s; using defaults", _SETTINGS_FILE)
        return {}


def save_settings(settings: dict) -> None:
    """Persist settings to disk, creating the directory if needed."""
    _SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    _SETTINGS_FILE.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.debug("Settings saved to %s", _SETTINGS_FILE)


def get_file_search_stores(settings: dict | None = None) -> list[str]:
    """Return the configured file-search store names, or an empty list."""
    s = settings if settings is not None else load_settings()
    return s.get("file_search_stores", [])


def set_file_search_stores(store_names: list[str], settings: dict | None = None) -> None:
    """Persist the given store names, merging with any existing settings."""
    s = settings if settings is not None else load_settings()
    s["file_search_stores"] = store_names
    save_settings(s)


def build_file_search_tool(store_names: list[str]) -> dict | None:
    """Return a file_search tool dict for the API, or None if no stores are configured."""
    if not store_names:
        return None
    return {"type": "file_search", "file_search_store_names": list(store_names)}
