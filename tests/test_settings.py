"""Tests for marketia.settings — settings persistence helpers."""

from __future__ import annotations

import json

from marketia.settings import (
    build_file_search_tool,
    build_mcp_tools,
    get_file_search_stores,
    get_mcp_servers,
    load_settings,
    save_settings,
    set_file_search_stores,
    set_mcp_servers,
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


# ---------------------------------------------------------------------------
# MCP server settings
# ---------------------------------------------------------------------------


def test_get_mcp_servers_empty_by_default():
    assert get_mcp_servers({}) == []


def test_set_and_get_mcp_servers_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr("marketia.settings._SETTINGS_DIR", tmp_path)
    monkeypatch.setattr("marketia.settings._SETTINGS_FILE", tmp_path / "settings.json")

    servers = [{"name": "echo", "url": "https://echo.example.com", "allowed_tools": ["echo"]}]
    set_mcp_servers(servers)
    assert get_mcp_servers() == servers


def test_build_mcp_tools_returns_none_for_empty():
    assert build_mcp_tools([]) is None


def test_build_mcp_tools_basic():
    servers = [{"name": "s", "url": "https://s.example.com"}]
    result = build_mcp_tools(servers)
    assert result == [{"type": "mcp_server", "name": "s", "url": "https://s.example.com"}]


def test_build_mcp_tools_with_headers_and_allowed():
    servers = [
        {
            "name": "private",
            "url": "https://private.example.com",
            "headers": {"Authorization": "Bearer tok"},
            "allowed_tools": ["search"],
        }
    ]
    result = build_mcp_tools(servers)
    assert result[0]["headers"] == {"Authorization": "Bearer tok"}
    assert result[0]["allowed_tools"] == ["search"]


def test_auth_headers_not_saved_to_settings(tmp_path, monkeypatch):
    """Auth headers go through the in-memory tool dict only; settings store bare server configs."""
    monkeypatch.setattr("marketia.settings._SETTINGS_DIR", tmp_path)
    monkeypatch.setattr("marketia.settings._SETTINGS_FILE", tmp_path / "settings.json")

    set_mcp_servers(
        [{"name": "s", "url": "https://s.example.com", "headers": {"X-Token": "secret"}}]
    )
    raw = json.loads((tmp_path / "settings.json").read_text())
    for srv in raw.get("mcp_servers", []):
        assert "headers" not in srv, "Auth headers must not be persisted to settings file"
