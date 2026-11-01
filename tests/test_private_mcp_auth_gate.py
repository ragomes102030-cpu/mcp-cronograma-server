"""Private MCP authentication regression, isolated from lifespan and remote DB."""
from unittest.mock import patch

from starlette.testclient import TestClient
import api.index as adapter

BASE = "https://arquimedes-mcp-cronograma.vercel.app"


def test_private_auth_gate_never_initializes_database(monkeypatch):
    monkeypatch.setenv("MCP_API_TOKEN", "isolated-test-token")
    monkeypatch.setattr(adapter, "_MISSING", [])
    client = TestClient(adapter.app, base_url=BASE)
    with patch.object(adapter, "_load_private_app", side_effect=AssertionError("loaded before auth")):
        for headers in ({}, {"Authorization": "Bearer wrong"}):
            response = client.post("/mcp", headers=headers, json={})
            assert response.status_code == 401
            assert "access-control-allow-origin" not in response.headers
        assert response.headers["www-authenticate"].startswith("Bearer ")


def test_missing_private_token_returns_service_unavailable(monkeypatch):
    monkeypatch.delenv("MCP_API_TOKEN", raising=False)
    monkeypatch.setattr(adapter, "_MISSING", [])
    client = TestClient(adapter.app, base_url=BASE)
    response = client.post("/mcp", json={})
    assert response.status_code == 503
    assert response.json()["reason"] == "configuration_incomplete"


def test_authenticated_private_route_invokes_loader_without_network(monkeypatch):
    monkeypatch.setenv("MCP_API_TOKEN", "isolated-test-token")
    monkeypatch.setattr(adapter, "_MISSING", [])
    calls = []
    def unavailable():
        calls.append("authenticated")
        return None
    client = TestClient(adapter.app, base_url=BASE)
    with patch.object(adapter, "_load_private_app", side_effect=unavailable):
        response = client.post("/mcp", headers={"Authorization": "Bearer isolated-test-token"}, json={})
    assert response.status_code == 503
    assert response.json()["error"] == "Private MCP unavailable"
    assert calls == ["authenticated"]
