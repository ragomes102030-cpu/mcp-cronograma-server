import json
import threading
from http.server import HTTPServer
from urllib.request import Request, urlopen

from api.public_mcp import handler


def _post(server, payload, headers):
    request = Request(
        f"http://127.0.0.1:{server.server_port}/public-mcp",
        data=json.dumps(payload).encode(),
        headers={"Host": "arquimedes-mcp-cronograma.vercel.app",
                 "Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream", **headers},
        method="POST",
    )
    return urlopen(request, timeout=10)


def test_modern_response_has_complete_http_chunk_framing():
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        payload = {"jsonrpc": "2.0", "id": 1, "method": "server/discover",
                   "params": {"_meta": {
                       "io.modelcontextprotocol/protocolVersion": "2026-07-28"}}}
        with _post(server, payload, {"MCP-Protocol-Version": "2026-07-28",
                                     "Mcp-Method": "server/discover"}) as response:
            result = json.loads(response.read())
            assert response.status == 200
            assert response.headers.get("Transfer-Encoding") == "chunked"
        assert "2026-07-28" in result["result"]["supportedVersions"]
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_legacy_initialize_remains_available_through_direct_handler():
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        payload = {"jsonrpc": "2.0", "id": 2, "method": "initialize",
                   "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                              "clientInfo": {"name": "regression-test", "version": "1"}}}
        with _post(server, payload, {"MCP-Protocol-Version": "2025-03-26"}) as response:
            body = json.loads(response.read())
            assert response.status == 200
            assert response.headers.get("Transfer-Encoding") == "chunked"
        assert "result" in body
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
