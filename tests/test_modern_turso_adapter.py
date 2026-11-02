"""Native libsql contract and opt-in adapter regression without remote secrets."""
import sqlite3
import sys
from types import SimpleNamespace

import pytest

import models
from models import atividades, baseline, db as database
from models.modern_turso import ModernTursoClient


def test_native_official_libsql_dbapi_local_contract():
    import libsql
    conn = libsql.connect(database=":memory:")
    try:
        conn.execute("CREATE TABLE qa (id TEXT PRIMARY KEY, value INTEGER)")
        conn.execute("INSERT INTO qa VALUES (?, ?)", ("a", 7))
        conn.commit()
        assert conn.execute("SELECT value FROM qa WHERE id = ?", ("a",)).fetchone()[0] == 7
    finally:
        conn.close()


def test_modern_adapter_executes_and_rolls_back_batch(tmp_path, monkeypatch):
    path = tmp_path / "modern-qa.db"
    def local_connect(*, database, auth_token):
        assert database == "https://qa-modern.invalid"
        assert auth_token == "qa-token"
        return sqlite3.connect(path)

    monkeypatch.setitem(sys.modules, "libsql", SimpleNamespace(connect=local_connect))
    client = ModernTursoClient("https://qa-modern.invalid", "qa-token")
    client.execute("CREATE TABLE qa (id TEXT PRIMARY KEY, qty INTEGER)")
    client.batch([("INSERT INTO qa VALUES (?, ?)", ["a", 1]),
                  ("INSERT INTO qa VALUES (?, ?)", ["b", 2])])
    assert client.execute("SELECT COUNT(*) AS n FROM qa").rows == [(2,)]

    with pytest.raises(sqlite3.IntegrityError):
        client.batch([("INSERT INTO qa VALUES (?, ?)", ["c", 3]),
                      ("INSERT INTO qa VALUES (?, ?)", ["a", 99])])
    assert client.execute("SELECT id FROM qa ORDER BY id").rows == [("a",), ("b",)]
    assert client.execute("SELECT qty FROM qa WHERE id = :1", [ "b" ]).rows == [(2,)]


def test_opt_in_modern_driver_models_roundtrip(tmp_path, monkeypatch):
    path = tmp_path / "modern-integration.db"
    def local_connect(*, database, auth_token):
        return sqlite3.connect(path)
    monkeypatch.setitem(sys.modules, "libsql", SimpleNamespace(connect=local_connect))
    monkeypatch.setenv("TURSO_DRIVER", "libsql")
    monkeypatch.setattr(database, "_TURSO_URL", "https://qa-modern.invalid")
    monkeypatch.setattr(database, "_TURSO_TOKEN", "qa-token")
    monkeypatch.setattr(database, "_turso_client", None)
    monkeypatch.setattr(baseline, "_TURSO_URL", "https://qa-modern.invalid")
    monkeypatch.setattr(atividades, "validar_eap_ref",
                        lambda _pid, ref: {"encontrado": True, "eap_ref": ref})
    models.init_db()
    activity = models.criar_atividade({
        "project_id": "isolated-modern", "nome": "Fundacao QA",
        "eap_ref": "qa.1", "duracao_dias": 4,
    })
    first = models.salvar_baseline("isolated-modern", "Inicial")
    models.atualizar_atividade(activity["id"], {"duracao_dias": 6})
    second = models.salvar_baseline("isolated-modern", "Rev 1")
    rows = models.listar_baselines("isolated-modern")
    assert len(rows) == 2
    assert {r["id"] for r in rows if r["ativa"]} == {second["id"]}
    assert first["id"] in {r["id"] for r in rows}
    old = models.comparar_baseline(first["id"])
    assert old["comparacao"][0]["duracao_baseline"] == 4
    assert old["comparacao"][0]["duracao_atual"] == 6
    assert models.buscar_atividade(activity["id"])["duracao_dias"] == 6


def test_modern_adapter_rejects_insecure_urls():
    with pytest.raises(ValueError, match="HTTPS"):
        ModernTursoClient("http://unsafe.invalid", "token")
    with pytest.raises(ValueError, match="auth token"):
        ModernTursoClient("https://safe.invalid", "")
