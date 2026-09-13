"""Conexão SQLite/Turso e schema do cronograma (PERT/CPM).

Mesmo padrão do mcp-eap-server: SQLite local por padrão; se ``TURSO_URL``/
``TURSO_TOKEN`` estiverem configuradas, usa Turso via ``libsql_client`` —
necessário porque o disco do Render não é persistente entre deploys (um
redeploy apagaria o banco local, perdendo atividades/dependências/baseline).

Cada atividade referencia um ``eap_id``/``uid`` do mcp-eap-server por
STRING (``eap_ref``), nunca por chave estrangeira de banco — os dois
serviços não compartilham banco de dados nem Turso (cada um com seu
próprio banco remoto).
"""

from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent.parent / "cronograma.db"

DEFAULT_PROJECT_ID = "default"

_TURSO_URL = os.environ.get("TURSO_URL", "")
_TURSO_TOKEN = os.environ.get("TURSO_TOKEN", "")


SCHEMA = """
CREATE TABLE IF NOT EXISTS atividade (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL,
    eap_ref         TEXT NOT NULL,
    nome            TEXT NOT NULL,
    duracao_dias    REAL,
    duracao_otimista    REAL,
    duracao_provavel    REAL,
    duracao_pessimista  REAL,
    percentual_concluido REAL NOT NULL DEFAULT 0,
    data_inicio_planejada TEXT,
    data_fim_planejada    TEXT,
    data_inicio_real      TEXT,
    data_fim_real         TEXT,
    es REAL, ef REAL, ls REAL, lf REAL, folga_total REAL, folga_livre REAL,
    critica INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_atividade_project ON atividade(project_id);
CREATE INDEX IF NOT EXISTS ix_atividade_eap_ref  ON atividade(eap_ref);

CREATE TABLE IF NOT EXISTS dependencia (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL,
    predecessora_id TEXT NOT NULL,
    sucessora_id    TEXT NOT NULL,
    tipo            TEXT NOT NULL DEFAULT 'TI',
    lag_dias        REAL NOT NULL DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (predecessora_id) REFERENCES atividade(id),
    FOREIGN KEY (sucessora_id) REFERENCES atividade(id)
);
CREATE INDEX IF NOT EXISTS ix_dep_project ON dependencia(project_id);
CREATE INDEX IF NOT EXISTS ix_dep_pred ON dependencia(predecessora_id);
CREATE INDEX IF NOT EXISTS ix_dep_suc  ON dependencia(sucessora_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_dep_par ON dependencia(predecessora_id, sucessora_id);

CREATE TABLE IF NOT EXISTS baseline (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL,
    nome            TEXT NOT NULL,
    criado_em       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS baseline_atividade (
    baseline_id     TEXT NOT NULL,
    atividade_id    TEXT NOT NULL,
    data_inicio_planejada TEXT,
    data_fim_planejada    TEXT,
    duracao_dias    REAL,
    PRIMARY KEY (baseline_id, atividade_id),
    FOREIGN KEY (baseline_id) REFERENCES baseline(id)
);

CREATE TABLE IF NOT EXISTS idempotency (
    request_id  TEXT PRIMARY KEY,
    tool_name   TEXT NOT NULL,
    response    TEXT NOT NULL,
    created_at  TEXT DEFAULT (datetime('now'))
);
"""

TIPOS_DEPENDENCIA_VALIDOS = {"TI", "II", "TT", "IT"}


def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _gerar_id(prefixo: str) -> str:
    return f"{prefixo}-{uuid.uuid4().hex[:12]}"


def _to_dict(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row) if not isinstance(row, dict) else row


def _to_list(rows: list[Any]) -> list[dict[str, Any]]:
    return [dict(r) if not isinstance(r, dict) else r for r in rows]


def _normalizar_turso_url(url: str) -> str:
    """Turso novos (ex.: *.aws-us-east-1.turso.io) recusam o handshake
    WebSocket do Hrana (400); o transporte HTTP (https://) funciona.
    Converte o scheme ``libsql://``/``ws(s)://`` em ``http(s)://``.
    """
    if url.startswith("libsql://"):
        return "https://" + url[len("libsql://"):]
    if url.startswith("wss://"):
        return "https://" + url[len("wss://"):]
    if url.startswith("ws://"):
        return "http://" + url[len("ws://"):]
    return url


_turso_client: Any = None


def _get_turso_client() -> Any:
    """ClientSync único (evita vazar uma sessão aiohttp a cada _connect())."""
    global _turso_client
    if _turso_client is None:
        import libsql_client
        _turso_client = libsql_client.create_client_sync(
            url=_normalizar_turso_url(_TURSO_URL), auth_token=_TURSO_TOKEN
        )
    return _turso_client


class _TursoConn:
    """Wrapper que emula a API sqlite3 usando libsql_client (Turso)."""

    def __init__(self) -> None:
        self._client = _get_turso_client()

    def execute(self, sql: str, params: tuple = ()) -> "_TursoCursor":
        converted = sql
        for i, _ in enumerate(params, start=1):
            converted = converted.replace("?", f":{i}", 1)
        result = self._client.execute(converted, list(params))
        return _TursoCursor(result)

    def executescript(self, script: str) -> None:
        for stmt in script.split(";"):
            stmt = stmt.strip()
            if stmt:
                self.execute(stmt)

    def commit(self) -> None:
        pass

    def __enter__(self) -> "_TursoConn":
        return self

    def __exit__(self, *exc: object) -> None:
        pass


class _TursoCursor:
    """Wrapper de resultado que emula .fetchone() / .fetchall() do sqlite3."""

    def __init__(self, result: Any) -> None:
        self._rows = [dict(zip(result.columns, row)) for row in result.rows]

    def fetchone(self) -> dict[str, Any] | None:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[dict[str, Any]]:
        return self._rows


def _connect() -> "_TursoConn | sqlite3.Connection":
    """Abre conexão: Turso (se ``TURSO_URL`` configurada) ou sqlite3 local.

    Resolve ``DB_PATH`` via ``from . import DB_PATH`` (não a constante deste
    módulo) de propósito: assim ``monkeypatch.setattr(models, "DB_PATH", ...)``
    nos testes (que altera o atributo do PACOTE) isola o banco corretamente
    mesmo com a lógica de conexão morando em ``db.py`` (mesma lição aprendida
    da mesma armadilha no mcp-eap-server).
    """
    if _TURSO_URL:
        return _TursoConn()
    from . import DB_PATH as _db_path
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Cria as tabelas caso ainda não existam. Idempotente."""
    with _connect() as conn:
        conn.executescript(SCHEMA)
        conn.commit()
