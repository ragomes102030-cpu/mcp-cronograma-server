"""Private MCP must authenticate before importing the database-backed server.

No real credentials, network access, database writes, or production data.
"""
import importlib
from unittest.mock import patch

from starlette.testclient import TestClient


def test_private_auth_gate_never_initializes_database(monkeypatch):
    monkeypatch.setenv("MCP_API_TOKEN", "isolated-test-token")
    monkeypatch.setenv("TURSO_URL", "https://unreachable.invalid")
    monkeypatch.setenv("TURSO_TOKEN", "isolated-fake-token")
    monkeypatch.setenv("EAP_SERVER_URL", "https://unreachable.invalid")
    monkeypatch.setenv("EAP_API_TOKEN", "isolated-fake-token")
    import api.index as adapter
    adapter = importlib.reload(adapter)
    with patch.object(adapter, "_load_private_app", side_effect=AssertionError("private import before auth")):
        with TestClient(adapter.app, base_url="https://arquimedes-mcp-cronograma.vercel.app") as client:
            response = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
            assert response.status_code == 401
            assert "access-control-allow-origin" not in response.headers
            assert response.headers["www-authenticate"].startswith("Bearer ")
            response = client.post("/mcp", headers={"Authorization": "Bearer wrong"}, json={})
            assert response.status_code == 401
            assert client.get("/public-mcp").status_code == 200
    importlib.reload(adapter)


def test_authenticated_private_route_invokes_loader_without_network(monkeypatch):
    monkeypatch.setenv("MCP_API_TOKEN", "isolated-test-token")
    monkeypatch.setenv("TURSO_URL", "https://unreachable.invalid")
    monkeypatch.setenv("TURSO_TOKEN", "isolated-fake-token")
    monkeypatch.setenv("EAP_SERVER_URL", "https://unreachable.invalid")
    monkeypatch.setenv("EAP_API_TOKEN", "isolated-fake-token")
    import api.index as adapter
    adapter = importlib.reload(adapter)
    calls = []
    def unavailable():
        calls.append("authenticated")
        return None
    with patch.object(adapter, "_load_private_app", side_effect=unavailable):
        with TestClient(adapter.app, base_url="https://arquimedes-mcp-cronograma.vercel.app") as client:
            response = client.post("/mcp", headers={"Authorization": "Bearer isolated-test-token"}, json={})
            assert response.status_code == 503
            assert response.json()["error"] == "Private MCP unavailable"
    assert calls == ["authenticated"]
    importlib.reload(adapter)
