"""Authenticated, stateless ASGI adapter for Vercel Python Functions.

Root app.py explicitly imports this entrypoint, so server.py stays available
for Render without triggering its SQLite startup side effects on Vercel.
"""
from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os

from public_mcp import public_app as _public_app
from mcp_public_origins import allowed_public_origins

# Vercel Marketplace Turso provides different names from the legacy Render setup.
if os.environ.get("VERCEL") == "1":
    if not os.environ.get("TURSO_URL") and os.environ.get("TURSO_DATABASE_URL"):
        os.environ["TURSO_URL"] = os.environ["TURSO_DATABASE_URL"]
    if not os.environ.get("TURSO_TOKEN") and os.environ.get("TURSO_AUTH_TOKEN"):
        os.environ["TURSO_TOKEN"] = os.environ["TURSO_AUTH_TOKEN"]

_REQUIRED_DB = ("TURSO_URL", "TURSO_TOKEN", "EAP_SERVER_URL", "EAP_API_TOKEN")
_MISSING = [key for key in ("MCP_API_TOKEN", *_REQUIRED_DB) if not os.environ.get(key)]
_mcp_app = None
_internal_lookup = None
_PRIVATE_STARTUP_ERROR = None
# Only start private MCP after a valid bearer-token request. Public lifespan
# startup must never connect to Turso or import the private server.
_private_lifespan_lock = None
_private_transport_task = None
_private_transport_started_app = None
_private_transport_stop = None
_private_transport_ready = None


def _load_private_app():
    """Import private server only after authenticated private request.

    Public MCP must never wait for remote database startup during module import.
    """
    global _mcp_app, _PRIVATE_STARTUP_ERROR
    if _mcp_app is not None or _MISSING:
        return _mcp_app
    try:
        from server import app as private_app
        _mcp_app = private_app
        _PRIVATE_STARTUP_ERROR = None
    except Exception as exc:
        _PRIVATE_STARTUP_ERROR = type(exc).__name__
        import logging
        logging.getLogger(__name__).exception("Private MCP startup failed")
    return _mcp_app


async def _send_json(send, status, payload, *, challenge=False):
    data = json.dumps(payload).encode("utf-8")
    headers = [(b"content-type", b"application/json"), (b"cache-control", b"no-store")]
    if challenge:
        headers.append((b"www-authenticate", b'Bearer realm="mcp"'))
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": data})


async def _empty_lifespan(receive, send):
    while True:
        event = await receive()
        if event["type"] == "lifespan.startup":
            await send({"type": "lifespan.startup.complete"})
        elif event["type"] == "lifespan.shutdown":
            await send({"type": "lifespan.shutdown.complete"})
            return


async def _lifespan_both(receive, send):
    """Start the public MCP only; never touch Turso on public startup."""
    global _private_lifespan_lock, _private_transport_task
    global _private_transport_started_app, _private_transport_stop, _private_transport_ready
    event = await receive()
    if event["type"] != "lifespan.startup":
        return
    try:
        async with _public_app.router.lifespan_context(_public_app):
            _private_lifespan_lock = asyncio.Lock()
            _private_transport_task = None
            _private_transport_started_app = None
            _private_transport_stop = asyncio.Event()
            _private_transport_ready = None
            try:
                await send({"type": "lifespan.startup.complete"})
                while True:
                    event = await receive()
                    if event["type"] == "lifespan.shutdown":
                        break
            finally:
                # The private transport owns its lifespan in a dedicated task.
                # Signal it to shut down, then await it before closing public MCP.
                if _private_transport_task is not None:
                    _private_transport_stop.set()
                    await _private_transport_task
                _private_lifespan_lock = None
                _private_transport_task = None
                _private_transport_started_app = None
                _private_transport_stop = None
                _private_transport_ready = None
            await send({"type": "lifespan.shutdown.complete"})
    except Exception as exc:
        await send({"type": "lifespan.startup.failed", "message": str(exc)})


async def _run_private_transport(private_app, ready, stop):
    """Enter and exit the private AnyIO task group in the SAME async task."""
    try:
        async with private_app.router.lifespan_context(private_app):
            if not ready.done():
                ready.set_result(True)
            await stop.wait()
    except Exception as exc:
        if not ready.done():
            ready.set_exception(exc)
        else:
            logging.getLogger(__name__).exception("Private transport exited unexpectedly")


async def _ensure_private_transport(private_app):
    """Initialize private MCP only after a valid bearer token is checked."""
    global _private_transport_task, _private_transport_started_app, _private_transport_ready
    lock, stop = _private_lifespan_lock, _private_transport_stop
    if lock is None or stop is None:
        return False
    async with lock:
        if _private_transport_started_app is private_app:
            return _private_transport_task is not None and not _private_transport_task.done()
        if _private_transport_started_app is not None:
            return False
        ready = asyncio.get_running_loop().create_future()
        _private_transport_started_app = private_app
        _private_transport_ready = ready
        _private_transport_task = asyncio.create_task(
            _run_private_transport(private_app, ready, stop)
        )
        return await ready


async def _reject_unsupported_sse_get(scope, send):
    """GET listener SSE is optional in MCP; serverless must not hold it open."""
    if scope.get("method") != "GET":
        return False
    headers = {key.lower(): val for key, val in scope.get("headers", [])}
    if b"text/event-stream" not in headers.get(b"accept", b""):
        return False
    await send({"type": "http.response.start", "status": 405,
                "headers": [(b"allow", b"POST, OPTIONS"),
                            (b"cache-control", b"no-store")]})
    await send({"type": "http.response.body", "body": b""})
    return True



# CORS is opt-in and scoped to the stateless PUBLIC MCP only.
# Private /mcp must never inherit these response headers.
_PUBLIC_CORS = (
    (b"access-control-allow-methods", b"POST, GET, HEAD, OPTIONS"),
    (b"access-control-allow-headers",
     b"Accept, Content-Type, MCP-Protocol-Version, Mcp-Method, Mcp-Name, "
     b"Mcp-Session-Id, Last-Event-ID"),
    (b"access-control-expose-headers", b"MCP-Protocol-Version, Mcp-Session-Id"),
    (b"access-control-max-age", b"600"),
    (b"vary", b"Origin"),
)


def _public_cors_sender(send, origin):
    async def send_public(message):
        if message["type"] == "http.response.start" and origin:
            message = dict(message, headers=list(message.get("headers", []))
                           + list(_PUBLIC_CORS)
                           + [(b"access-control-allow-origin", origin)])
        await send(message)

    return send_public


async def app(scope, receive, send):
    global _PRIVATE_STARTUP_ERROR
    if scope["type"] == "lifespan":
        await _lifespan_both(receive, send)
        return
    if scope["type"] != "http":
        return
    path = scope.get("path", "")
    # TEMPORARY BRANCH ONLY: QA project ID guard prevents test routes in real MCP.
    if path in ("/_qa/readiness", "/_qa/roundtrip"):
        from . import qa_probe
        if os.environ.get("VERCEL_PROJECT_ID") != qa_probe.QA_PROJECT:
            await _send_json(send, 404, {"ok": False, "error": "Not found"})
            return
        if path == "/_qa/readiness" and scope.get("method") == "GET":
            await _send_json(send, 200, qa_probe.readiness())
            return
        if path == "/_qa/roundtrip" and scope.get("method") == "POST":
            headers = {k.lower(): v for k,v in scope.get("headers", [])}
            if not qa_probe.authorised(headers):
                await _send_json(send, 403, {"ok": False, "error": "QA authorization denied"})
                return
            from urllib.parse import parse_qs
            driver = parse_qs(scope.get("query_string", b"").decode()).get("driver", [""])[0]
            result = await asyncio.to_thread(qa_probe.run, driver)
            await _send_json(send, 200 if result.get("ok") else 503, result)
            return
        await _send_json(send, 405, {"ok": False, "error": "Unsupported QA method"})
        return
    if path in ("/healthz", "/api/healthz"):
        configured = not bool(_MISSING) and _PRIVATE_STARTUP_ERROR is None
        await _send_json(send, 200 if configured else 503, {"ok": configured, "configured": configured, "private_startup_error": _PRIVATE_STARTUP_ERROR})
        return
    # Public endpoint has its OWN tools and no access to project storage.
    # Private /mcp and /internal/eap-node still require MCP_API_TOKEN.
    if path.rstrip("/") == "/public-mcp":
        origin = next((value for key, value in scope.get("headers", [])
                       if key.lower() == b"origin"), b"")
        if origin and origin.decode("utf-8", "replace").lower() not in allowed_public_origins():
            await _send_json(send, 403, {"ok": False, "error": "Origin not allowed"})
            return
        send_public = _public_cors_sender(send, origin)
        # Claude may first probe the URL with an ordinary GET/HEAD before
        # negotiating MCP Streamable HTTP. Such probes need a stable success
        # status; real SSE GET and JSON-RPC POST continue to the MCP transport.
        method = scope.get("method", "GET")
        if method in ("GET", "HEAD") and b"text/event-stream" not in dict(
            (key.lower(), val) for key, val in scope.get("headers", [])
        ).get(b"accept", b""):
            if method == "HEAD":
                await send_public({"type": "http.response.start", "status": 200,
                            "headers": [(b"cache-control", b"no-store")]})
                await send_public({"type": "http.response.body", "body": b""})
            else:
                await _send_json(send_public, 200, {"ok": True,
                    "transport": "streamable-http", "endpoint": "/public-mcp",
                    "auth": "none", "capabilities": "stateless-calculations-only"})
            return
        if method == "OPTIONS":
            await send_public({"type": "http.response.start", "status": 204,
                        "headers": [(b"allow", b"GET, HEAD, POST, OPTIONS"),
                                    (b"cache-control", b"no-store")]})
            await send_public({"type": "http.response.body", "body": b""})
            return
        if await _reject_unsupported_sse_get(scope, send_public):
            return
        public_scope = dict(scope)
        public_scope["path"] = "/mcp"
        public_scope["raw_path"] = b"/mcp"
        await _public_app(public_scope, receive, send_public)
        return
    if path not in ("/mcp", "/api/index"):
        await _send_json(send, 404, {"ok": False, "error": "Not found"})
        return
    if _MISSING:
        await _send_json(send, 503, {"ok": False, "error": "Private MCP unavailable", "reason": "configuration_incomplete"})
        return
    headers = {key.lower(): val for key, val in scope.get("headers", [])}
    token = os.environ.get("MCP_API_TOKEN", "")
    if not token:
        await _send_json(send, 503, {"ok": False, "error": "Private MCP unavailable", "reason": "configuration_incomplete"})
        return
    expected = ("Bearer " + token).encode("utf-8")
    if not hmac.compare_digest(headers.get(b"authorization", b""), expected):
        await _send_json(send, 401, {"ok": False, "error": "Authentication required"}, challenge=True)
        return

    private_app = _load_private_app()
    if private_app is None:
        await _send_json(send, 503, {"ok": False, "error": "Private MCP unavailable", "reason": _PRIVATE_STARTUP_ERROR})
        return
    if await _reject_unsupported_sse_get(scope, send):
        return
    try:
        ready = await _ensure_private_transport(private_app)
    except Exception as exc:
        _PRIVATE_STARTUP_ERROR = type(exc).__name__
        logging.getLogger(__name__).exception("Private MCP transport startup failed")
        ready = False
    if not ready:
        await _send_json(send, 503, {"ok": False, "error": "Private MCP unavailable", "reason": "transport_unavailable"})
        return
    mcp_scope = dict(scope)
    mcp_scope["path"] = "/mcp"
    mcp_scope["raw_path"] = b"/mcp"
    await private_app(mcp_scope, receive, send)
