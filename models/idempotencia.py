"""Idempotência: mesmo request_id devolve a mesma resposta (evita duplicar
atividade/dependência em retry de cliente MCP)."""

from __future__ import annotations

import json
from typing import Any

from .db import _connect


def verificar_idempotencia(request_id: str | None) -> dict[str, Any] | None:
    if not request_id:
        return None
    with _connect() as conn:
        cursor = conn.execute(
            "SELECT response FROM idempotency WHERE request_id = ?", (request_id,)
        )
        row = cursor.fetchone()
    return json.loads(row["response"]) if row else None


def salvar_idempotencia(request_id: str | None, tool_name: str, response: Any) -> None:
    if not request_id:
        return
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO idempotency (request_id, tool_name, response) VALUES (?, ?, ?)",
            (request_id, tool_name, json.dumps(response)),
        )
        conn.commit()
