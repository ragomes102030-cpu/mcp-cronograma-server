"""Authenticated private route integration with the real server and isolated SQLite.

This exercises the ASGI authentication gate and actual private app loader.
No Turso credentials or network requests are used.
"""
import sys
from contextlib import asynccontextmanager

from starlette.testclient import TestClient

import api.index as adapter
import models
from models import db as database


def test_authenticated_private_request_with_real_local_server(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "DB_PATH", tmp_path / "isolated-auth.db")
    monkeypatch.setattr(database, "_TURSO_URL", "")
    monkeypatch.setattr(database, "_TURSO_TOKEN", "")
    monkeypatch.setenv("MCP_API_TOKEN", "test-only-secret")
    monkeypatch.setattr(adapter, "_MISSING", [])
    monkeypatch.setattr(adapter, "_mcp_app", None)
    monkeypatch.setattr(adapter, "_PRIVATE_STARTUP_ERROR", None)
    monkeypatch.delitem(sys.modules, "server", raising=False)

    client = TestClient(adapter.app, base_url="http://testserver")
    denied = client.post("/mcp", headers={"Authorization": "Bearer incorrect"}, json={})
    assert denied.status_code == 401
    assert adapter._mcp_app is None

    # An authenticated but malformed MCP request must reach the real MCP app,
    # not be rejected by the auth gate or trigger a production DB connection.
    # Start the MCP ASGI lifespan so the transport task group is initialized.
    with client:
        # A public lifespan must not import private MCP or initialize Turso.
        assert adapter._mcp_app is None
        response = client.post("/mcp", headers={
        "Authorization": "Bearer test-only-secret",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }, json={"jsonrpc": "2.0", "id": 1, "method": "invalid/method"})
    assert response.status_code != 401
    assert adapter._mcp_app is not None
    assert adapter._PRIVATE_STARTUP_ERROR is None
    assert not (tmp_path / "isolated-auth.db").exists() or (tmp_path / "isolated-auth.db").is_file()


def test_public_lifespan_never_loads_private_server(monkeypatch):
    """Public startup/health must not touch Turso even when private is configured."""
    monkeypatch.setattr(adapter, "_MISSING", [])
    monkeypatch.setattr(adapter, "_mcp_app", None)
    monkeypatch.setattr(adapter, "_PRIVATE_STARTUP_ERROR", None)
    monkeypatch.setenv("MCP_API_TOKEN", "test-only-secret")

    def unexpected_private_startup():
        raise AssertionError("private MCP loaded during public startup")

    monkeypatch.setattr(adapter, "_load_private_app", unexpected_private_startup)

    # The real SDK session manager is single-use and was already exercised by
    # the authenticated test above. Only bypass its *public* lifecycle here;
    # this regression specifically verifies that private startup is not called.
    @asynccontextmanager
    async def isolated_public_lifespan(_app):
        yield

    monkeypatch.setattr(adapter._public_app.router, "lifespan_context", isolated_public_lifespan)
    with TestClient(adapter.app, base_url="http://testserver") as client:
        assert adapter._mcp_app is None
        health = client.get("/healthz")
        assert health.status_code == 200, health.text
        public = client.get("/public-mcp", headers={"Accept": "application/json"})
        assert public.status_code == 200, public.text
        assert public.json()["transport"] == "streamable-http"
        assert adapter._mcp_app is None
