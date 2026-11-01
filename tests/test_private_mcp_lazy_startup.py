"""Private MCP lazy startup tests; no Turso or external EAP connection."""
import sys
from types import SimpleNamespace

import api.index as adapter


def test_private_app_loads_only_on_demand_and_is_cached(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(adapter, "_MISSING", [])
    monkeypatch.setattr(adapter, "_mcp_app", None)
    monkeypatch.setattr(adapter, "_PRIVATE_STARTUP_ERROR", None)
    monkeypatch.setitem(sys.modules, "server", SimpleNamespace(app=sentinel))
    assert adapter._mcp_app is None
    assert adapter._load_private_app() is sentinel
    assert adapter._PRIVATE_STARTUP_ERROR is None
    monkeypatch.delitem(sys.modules, "server")
    assert adapter._load_private_app() is sentinel


def test_private_app_missing_configuration_never_imports_server(monkeypatch):
    monkeypatch.setattr(adapter, "_MISSING", ["TURSO_URL"])
    monkeypatch.setattr(adapter, "_mcp_app", None)
    monkeypatch.delitem(sys.modules, "server", raising=False)
    assert adapter._load_private_app() is None
    assert "server" not in sys.modules


def test_private_app_import_failure_fails_closed_without_leaking_details(monkeypatch):
    monkeypatch.setattr(adapter, "_MISSING", [])
    monkeypatch.setattr(adapter, "_mcp_app", None)
    monkeypatch.setattr(adapter, "_PRIVATE_STARTUP_ERROR", None)
    monkeypatch.setitem(sys.modules, "server", None)
    assert adapter._load_private_app() is None
    assert adapter._PRIVATE_STARTUP_ERROR == "ModuleNotFoundError"
