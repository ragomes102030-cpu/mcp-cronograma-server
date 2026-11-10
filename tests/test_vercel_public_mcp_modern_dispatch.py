import json
from pathlib import Path

from api.public_mcp import _dispatch_modern_jsonrpc


def test_modern_discover_and_tools_list_expose_chronogram_tools():
    discover = _dispatch_modern_jsonrpc({"jsonrpc": "2.0", "id": 1,
                                         "method": "server/discover", "params": {}})
    listed = _dispatch_modern_jsonrpc({"jsonrpc": "2.0", "id": 2,
                                       "method": "tools/list", "params": {}})

    assert "2026-07-28" in discover["result"]["supportedVersions"]
    names = {tool["name"] for tool in listed["result"]["tools"]}
    assert names == {
        "calcular_duracao_com_evidencia", "calcular_cpm_com_evidencia",
        "calcular_cpm_com_calendario", "comparar_baseline_sem_persistencia",
        "diagnosticar_rede_cpm",
    }


def test_modern_call_runs_stateless_duration_calculation():
    response = _dispatch_modern_jsonrpc({
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "calcular_duracao_com_evidencia", "arguments": {
            "quantidade": 12, "produtividade": 3,
            "unidade": "m2", "unidade_produtividade": "m2",
        }},
    })

    result = response["result"]
    assert result["structuredContent"]["duracaoDias"] == 4
    assert result["structuredContent"]["persistido"] is False
    assert result["isError"] is False


def test_modern_unknown_method_returns_json_rpc_error():
    response = _dispatch_modern_jsonrpc({"jsonrpc": "2.0", "id": 4,
                                         "method": "not/a/method", "params": {}})
    assert response["error"]["code"] == -32601


def test_vercel_rewrites_keep_private_mcp_and_health_routes():
    config = json.loads((Path(__file__).parents[1] / "vercel.json").read_text(encoding="utf-8"))
    routes = {entry["source"]: entry["destination"] for entry in config["rewrites"]}

    assert routes["/public-mcp"] == "/api/public_mcp"
    assert routes["/mcp"] == "/api/index?__vercel_original_path=/mcp"
    assert routes["/healthz"] == "/api/index?__vercel_original_path=/healthz"
    assert routes["/api/healthz"] == "/api/index?__vercel_original_path=/api/healthz"
