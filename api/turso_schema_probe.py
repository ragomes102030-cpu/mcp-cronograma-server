"""Temporary, PREVIEW-ONLY, READ-ONLY Turso schema diagnostic.

Never merge into master; never expose credentials or SQL error messages.
"""
import json
import os
from http.server import BaseHTTPRequestHandler

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if os.environ.get("VERCEL_ENV") != "preview":
            self._send(404, {"ok": False})
            return
        try:
            import libsql_client
            url = os.environ.get("TURSO_URL") or os.environ.get("TURSO_DATABASE_URL", "")
            token = os.environ.get("TURSO_TOKEN") or os.environ.get("TURSO_AUTH_TOKEN", "")
            if not url or not token:
                self._send(503, {"ok": False, "category": "configuration_missing"})
                return
            if url.startswith("libsql://"):
                url = "https://" + url[len("libsql://"):]
            elif url.startswith("wss://"):
                url = "https://" + url[len("wss://"):]
            client = libsql_client.create_client_sync(url=url, auth_token=token)
            try:
                ping = client.execute("SELECT 1 AS ping")
                schema = client.execute(
                    "SELECT COUNT(*) AS total FROM sqlite_master "
                    "WHERE type='table' AND name IN "
                    "('atividade','dependencia','baseline','baseline_ativa','baseline_atividade','idempotency')"
                )
                self._send(200, {"ok": True,
                    "ping": bool(ping.rows and ping.rows[0][0] == 1),
                    "expected_tables_count": int(schema.rows[0][0]),
                    "expected_tables_total": 6,
                    "read_only": True})
            finally:
                client.close()
        except Exception as exc:
            # Do not reveal SQL, network endpoints, tokens or server messages.
            self._send(503, {"ok": False, "category": type(exc).__name__,
                             "read_only": True})

    def _send(self, status, body):
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
