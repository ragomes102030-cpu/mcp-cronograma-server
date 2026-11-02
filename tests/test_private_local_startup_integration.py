"""Integration smoke: import real private server with disposable SQLite.

No Turso token, network connection, or external EAP calls are used.
"""
import sys

import api.index as adapter
import models
from models import db as database


def test_real_private_server_import_with_disposable_sqlite(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "DB_PATH", tmp_path / "private-startup.db")
    monkeypatch.setattr(database, "_TURSO_URL", "")
    monkeypatch.setattr(database, "_TURSO_TOKEN", "")
    monkeypatch.setattr(adapter, "_MISSING", [])
    monkeypatch.setattr(adapter, "_mcp_app", None)
    monkeypatch.setattr(adapter, "_PRIVATE_STARTUP_ERROR", None)
    monkeypatch.delitem(sys.modules, "server", raising=False)

    private_app = adapter._load_private_app()
    assert private_app is not None
    assert adapter._PRIVATE_STARTUP_ERROR is None
    assert adapter._load_private_app() is private_app

    # Validate the local DB independently; never initialize remote Turso.
    models.init_db()
    assert (tmp_path / "private-startup.db").exists()
    with database._connect() as conn:
        tables = {row["name"] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    assert {"atividade", "dependencia", "baseline", "baseline_ativa"} <= tables
