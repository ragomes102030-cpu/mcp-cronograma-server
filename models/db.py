"""Conexão SQLite e schema do cronograma (PERT/CPM).

Segue o mesmo padrão do mcp-eap-server: SQLite local por padrão, com
possibilidade futura de apontar para Turso (mesma técnica de wrapper, não
implementada ainda nesta v1 — ver TODO em ``_connect``).

Cada atividade referencia um ``eap_id``/``uid`` do mcp-eap-server por
STRING (``eap_ref``), nunca por chave estrangeira de banco — os dois
serviços não compartilham banco de dados. A validação de que o ``eap_ref``
realmente existe na EAP é responsabilidade da camada de tools
(``server.py``), que pode chamar o mcp-eap-server via HTTP quando
``EAP_SERVER_URL`` estiver configurada (ver ``eap_client.py``).
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent.parent / "cronograma.db"

DEFAULT_PROJECT_ID = "default"


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


def _connect() -> sqlite3.Connection:
    """Abre conexão SQLite local.

    Resolve ``DB_PATH`` via ``from . import DB_PATH`` (não a constante deste
    módulo) de propósito: assim ``monkeypatch.setattr(models, "DB_PATH", ...)``
    nos testes (que altera o atributo do PACOTE) isola o banco corretamente
    mesmo com a lógica de conexão morando em ``db.py`` (mesma lição aprendida
    da mesma armadilha no mcp-eap-server).

    TODO (v2): suporte a Turso via o mesmo wrapper HTTP usado no
    mcp-eap-server, quando este serviço precisar de persistência que
    sobreviva a redeploy sem disco persistente.
    """
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
