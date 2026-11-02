"""End-to-end Turso data-model contract, with a hard guard for remote writes.

The default test runs against a real SQLite engine through the same Turso
compatibility wrapper and atomic batch interface. A remote run MUST use a
separate, disposable Turso database and explicitly opt into writes.
No real EAP service or production project is touched.
"""
from __future__ import annotations

import os
import sqlite3
from types import SimpleNamespace
from urllib.parse import urlparse
from uuid import uuid4

import pytest

import models
from models import atividades, baseline, db as database


class SQLiteBackedTurso:
    """Fake network boundary, real SQLite statements and atomic transactions."""

    def __init__(self):
        self.conn = sqlite3.connect(":memory:", isolation_level=None)

    def execute(self, sql, params=()):
        cursor = self.conn.execute(sql, params)
        return SimpleNamespace(
            columns=[col[0] for col in cursor.description] if cursor.description else [],
            rows=cursor.fetchall() if cursor.description else [],
        )

    def batch(self, statements):
        self.conn.execute("BEGIN")
        try:
            for sql, params in statements:
                self.conn.execute(sql, params)
            self.conn.execute("COMMIT")
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise


def _run_roundtrip(project_id):
    a = models.criar_atividade({
        "project_id": project_id, "eap_ref": "qa.1",
        "nome": "Fundacoes QA", "duracao_dias": 5,
    })
    b = models.criar_atividade({
        "project_id": project_id, "eap_ref": "qa.2",
        "nome": "Estrutura QA", "duracao_dias": 8,
    })
    assert models.contar_atividades(project_id) == 2
    assert models.buscar_atividade(a["id"])["nome"] == "Fundacoes QA"

    edge = models.criar_dependencia(a["id"], b["id"], "TI", project_id=project_id)
    assert edge["predecessora_id"] == a["id"]
    assert len(models.listar_dependencias(project_id)) == 1
    assert models.validar_dependencias(project_id)["resumo"]["rede_valida"]

    first = models.salvar_baseline(project_id, "Contratual QA")
    models.atualizar_atividade(b["id"], {"duracao_dias": 11})
    assert models.buscar_atividade(b["id"])["duracao_dias"] == 11
    second = models.salvar_baseline(project_id, "Revisao QA")
    versions = models.listar_baselines(project_id)
    assert len(versions) == 2
    assert sum(bool(row["ativa"]) for row in versions) == 1
    assert next(v for v in versions if v["ativa"])["id"] == second["id"]
    assert len(models.comparar_baseline(first["id"])["comparacao"]) == 2
    assert len(models.comparar_baseline(second["id"])["comparacao"]) == 2

    # Duplicate PK on the first statement of a batch must not replace the
    # active baseline or delete historical snapshots.
    original_id_generator = baseline._gerar_id
    try:
        baseline._gerar_id = lambda _prefix: first["id"]
        with pytest.raises(Exception):
            models.salvar_baseline(project_id, "Revisao invalida QA")
    finally:
        baseline._gerar_id = original_id_generator
    current = models.listar_baselines(project_id)
    assert len(current) == 2
    assert next(v for v in current if v["ativa"])["id"] == second["id"]

    with pytest.raises(ValueError, match="depend"):
        models.deletar_atividade(a["id"])
    assert models.deletar_dependencia(edge["id"])["deletado"]
    assert models.deletar_atividade(a["id"])["deletado"]
    assert models.contar_atividades(project_id) == 1
    return project_id


def _guard_disposable_url():
    target = os.environ.get("TURSO_TEST_DATABASE_URL", "")
    secret = os.environ.get("TURSO_TEST_AUTH_TOKEN", "")
    production = os.environ.get("TURSO_PRODUCTION_DATABASE_URL", "")
    confirmation = os.environ.get("TURSO_REMOTE_TEST_CONFIRM", "")
    if not target or not secret:
        pytest.skip("Separate disposable Turso URL/token not configured.")
    if confirmation != "YES_DISPOSABLE_WRITES":
        pytest.skip("Remote writes require TURSO_REMOTE_TEST_CONFIRM=YES_DISPOSABLE_WRITES.")
    if not production:
        pytest.fail("Set TURSO_PRODUCTION_DATABASE_URL to reject accidental production targeting.")

    def hostname(url):
        normalized = database._normalizar_turso_url(url)
        parsed = urlparse(normalized)
        if parsed.scheme != "https" or not parsed.hostname:
            pytest.fail("Remote test URL must be HTTPS with a hostname.")
        return parsed.hostname

    test_host, prod_host = hostname(target), hostname(production)
    if test_host == prod_host:
        pytest.fail("Refusing to write to the production Turso hostname.")
    if not test_host.startswith(("qa-", "test-", "sandbox-", "disposable-")):
        pytest.fail("Disposable Turso database hostname must start with qa-, test-, sandbox- or disposable-.")
    return target, secret


def _setup_driver(monkeypatch, url, token, client=None):
    monkeypatch.setattr(database, "_TURSO_URL", url)
    monkeypatch.setattr(database, "_TURSO_TOKEN", token)
    monkeypatch.setattr(database, "_turso_client", None)
    monkeypatch.setattr(baseline, "_TURSO_URL", url)
    if client is not None:
        monkeypatch.setattr(database, "_get_turso_client", lambda: client)
        monkeypatch.setattr(baseline, "_get_turso_client", lambda: client)
    monkeypatch.setattr(atividades, "validar_eap_ref",
                        lambda _pid, ref: {"encontrado": True, "eap_ref": ref})


def test_full_turso_wrapper_contract_on_disposable_sqlite(monkeypatch):
    client = SQLiteBackedTurso()
    try:
        _setup_driver(monkeypatch, "https://qa-disposable.invalid", "not-a-real-token", client)
        models.init_db()
        _run_roundtrip("qa-local-" + uuid4().hex[:12])
    finally:
        client.conn.close()


@pytest.mark.remote_turso
def test_full_remote_disposable_turso_roundtrip(monkeypatch):
    """Writes only to separately provisioned QA database. Never production."""
    target, secret = _guard_disposable_url()
    _setup_driver(monkeypatch, target, secret)
    project_id = "qa-remote-" + uuid4().hex[:12]
    client = None
    try:
        client = database._get_turso_client()
        models.init_db()
        _run_roundtrip(project_id)
    finally:
        # Cleanup ONLY our uniquely named QA project in the disposable database.
        # If the transport failed, leave the QA database for investigation.
        if client is not None:
            try:
                with database._connect() as conn:
                    conn.execute(
                        "DELETE FROM baseline_atividade WHERE baseline_id IN "
                        "(SELECT id FROM baseline WHERE project_id = ?)", (project_id,))
                    conn.execute("DELETE FROM baseline_ativa WHERE project_id = ?", (project_id,))
                    conn.execute("DELETE FROM baseline WHERE project_id = ?", (project_id,))
                    conn.execute("DELETE FROM dependencia WHERE project_id = ?", (project_id,))
                    conn.execute("DELETE FROM atividade WHERE project_id = ?", (project_id,))
                    conn.commit()
            finally:
                client.close()
