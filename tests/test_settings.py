"""Tests for marketia.settings — settings persistence helpers."""

from __future__ import annotations

import json

from marketia.settings import (
    build_file_search_tool,
    get_file_search_stores,
    load_settings,
    save_settings,
    set_file_search_stores,
)


def test_load_settings_returns_empty_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("marketia.settings._SETTINGS_FILE", tmp_path / "missing.json")
    assert load_settings() == {}


def test_save_and_load_roundtrip(tmp_path, monkeypatch):
    f = tmp_path / "settings.json"
    monkeypatch.setattr("marketia.settings._SETTINGS_DIR", tmp_path)
    monkeypatch.setattr("marketia.settings._SETTINGS_FILE", f)
    save_settings({"foo": "bar"})
    assert load_settings() == {"foo": "bar"}


def test_load_settings_recovers_from_corrupt_file(tmp_path, monkeypatch):
    f = tmp_path / "settings.json"
    f.write_text("not json", encoding="utf-8")
    monkeypatch.setattr("marketia.settings._SETTINGS_FILE", f)
    assert load_settings() == {}


def test_get_file_search_stores_empty_by_default():
    assert get_file_search_stores({}) == []


def test_get_file_search_stores_returns_list():
    stores = ["fileSearchStores/a", "fileSearchStores/b"]
    assert get_file_search_stores({"file_search_stores": stores}) == stores


def test_set_file_search_stores_persists(tmp_path, monkeypatch):
    f = tmp_path / "settings.json"
    monkeypatch.setattr("marketia.settings._SETTINGS_DIR", tmp_path)
    monkeypatch.setattr("marketia.settings._SETTINGS_FILE", f)
    set_file_search_stores(["fileSearchStores/x"])
    data = json.loads(f.read_text())
    assert data["file_search_stores"] == ["fileSearchStores/x"]


def test_build_file_search_tool_returns_none_for_empty():
    assert build_file_search_tool([]) is None


def test_build_file_search_tool_returns_dict():
    stores = ["fileSearchStores/my-store"]
    result = build_file_search_tool(stores)
    assert result == {"type": "file_search", "file_search_store_names": stores}
