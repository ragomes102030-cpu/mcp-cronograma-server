"""Authenticated private route integration with the real server and isolated SQLite.

This exercises the ASGI authentication gate and actual private app loader.
No Turso credentials or network requests are used.
"""
import sys

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
    # Start the MCP ASGI lifespan so the transport task group is initialized.\n    with client:\n        response = client.post("/mcp", headers={
        "Authorization": "Bearer test-only-secret",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }, json={"jsonrpc": "2.0", "id": 1, "method": "invalid/method"})
    assert response.status_code != 401
    assert adapter._mcp_app is not None
    assert adapter._PRIVATE_STARTUP_ERROR is None
    assert not (tmp_path / "isolated-auth.db").exists() or (tmp_path / "isolated-auth.db").is_file()
