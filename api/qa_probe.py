"""TEMPORARY QA ONLY. Never merge into master or deploy to production project."""
from __future__ import annotations
import hashlib
import hmac
import os
from urllib.parse import urlparse
from uuid import uuid4

QA_PROJECT = "prj_JLxZLgUE1gLoVNTNb9SAcZLCRuKp"
QA_BRANCH = "qa/turso-e2e-20261102"
QA_AUTH_SHA256 = "5c499bc92b76139b091403c573c298f540a1b5748e0d9422ad1000c8d47e96e2"
QA_DB_NAME = "qa-cronograma-20261102"


def readiness():
    url = os.environ.get("TURSO_DATABASE_URL", "")
    hostname = urlparse(url.replace("libsql://", "https://")).hostname or ""
    project_ok = os.environ.get("VERCEL_PROJECT_ID") == QA_PROJECT
    qa_host_ok = hostname.startswith(QA_DB_NAME + "-") or hostname == QA_DB_NAME + ".turso.io"
    return {
        "ok": project_ok and qa_host_ok,
        "project_ok": project_ok,
        "qa_host_ok": qa_host_ok,
        "qa_name": QA_DB_NAME,
        "db_token_present": bool(os.environ.get("TURSO_AUTH_TOKEN")),
        "env": os.environ.get("VERCEL_ENV"),
        "git_branch": os.environ.get("VERCEL_GIT_COMMIT_REF"),
        "write_enabled": os.environ.get("QA_E2E_ALLOW") == "YES_DISPOSABLE_WRITES",
    }


def authorised(headers):
    header = headers.get(b"x-qa-auth", b"")
    digest = hashlib.sha256(header).hexdigest()
    return hmac.compare_digest(digest, QA_AUTH_SHA256)


def run(driver):
    if driver not in ("legacy", "libsql"):
        return {"ok": False, "reason": "unsupported_driver"}
    config = readiness()
    if (not config["ok"] or not config["db_token_present"]
        or config["env"] != "production" or config["git_branch"] != QA_BRANCH
        or not config["write_enabled"]):
        return {"ok": False, "reason": "qa_environment_guard", "guards": config}

    from models import atividades, baseline, db
    import models
    assert db._normalizar_turso_url(os.environ["TURSO_DATABASE_URL"]).startswith("https://")

    # Test branches only. No external project/EAP data is changed.
    prev_driver = os.environ.get("TURSO_DRIVER")
    os.environ["TURSO_DRIVER"] = driver
    cached = db._turso_client
    db._turso_client = None
    previous_validator = atividades.validar_eap_ref
    atividades.validar_eap_ref = lambda project_id, ref: {"encontrado": True, "eap_ref": ref}
    baseline._TURSO_URL = db._TURSO_URL
    pid = "qa-remote-" + uuid4().hex[:12]
    result = {"ok": False, "driver": driver, "project": pid, "checks": [], "cleaned": False}
    try:
        client = db._get_turso_client()
        assert client.execute("SELECT 1 AS ping").rows[0][0] == 1
        result["checks"].append("remote_select_1")
        models.init_db()
        expected = ("atividade", "dependencia", "baseline", "baseline_ativa",
                    "baseline_atividade", "idempotency")
        tables = client.execute("SELECT name FROM sqlite_master WHERE type='table'").rows
        present = {row[0] for row in tables}
        assert set(expected).issubset(present), present
        result["checks"].append("six_schema_tables")

        a = models.criar_atividade({"project_id":pid,"eap_ref":"qa.1",
            "nome":"Fundacoes QA","duracao_dias":5})
        b = models.criar_atividade({"project_id":pid,"eap_ref":"qa.2",
            "nome":"Estrutura QA","duracao_dias":8})
        assert models.contar_atividades(pid) == 2
        result["checks"].append("activity_create_read")
        dep = models.criar_dependencia(a["id"], b["id"], "TI", project_id=pid)
        assert len(models.listar_dependencias(pid)) == 1
        assert models.validar_dependencias(pid)["resumo"]["rede_valida"]
        result["checks"].append("dependency_create_validate")
        bl1 = models.salvar_baseline(pid, "Base contratual")
        models.atualizar_atividade(b["id"], {"duracao_dias":11})
        bl2 = models.salvar_baseline(pid, "Base revisada")
        versions = models.listar_baselines(pid)
        assert len(versions)==2 and sum(bool(v["ativa"]) for v in versions)==1
        assert next(v for v in versions if v["ativa"])["id"] == bl2["id"]
        cmp = models.comparar_baseline(bl1["id"])
        assert len(cmp["comparacao"]) == 2
        assert any(x.get("desvio_duracao_dias") == 3 for x in cmp["comparacao"])
        result["checks"].append("baselines_revision_and_history")

        # The first statement succeeds and the second fails: both MUST roll back.
        rid = "qa-rollback-" + uuid4().hex[:14]
        stmts = [
            ("INSERT INTO idempotency (request_id, tool_name, response) VALUES (?, ?, ?)",
             [rid,"qa","first"]),
            ("INSERT INTO idempotency (request_id, tool_name, response) VALUES (?, ?, ?)",
             [rid,"qa","duplicate"]),
        ]
        try:
            client.batch(stmts)
        except Exception:
            pass
        else:
            raise AssertionError("failed batch unexpectedly committed")
        assert client.execute("SELECT COUNT(*) FROM idempotency WHERE request_id=?", [rid]).rows[0][0] == 0
        result["checks"].append("failed_second_statement_full_rollback")

        try:
            models.deletar_atividade(a["id"])
        except ValueError:
            pass
        else:
            raise AssertionError("deletion with active dependency accepted")
        models.deletar_dependencia(dep["id"])
        models.deletar_atividade(a["id"])
        assert models.contar_atividades(pid) == 1
        result["checks"].append("dependency_guard_and_delete")
        result["ok"] = True
    except Exception as exc:
        result["error_type"] = type(exc).__name__
        result["error_detail"] = str(exc)[:230]
    finally:
        try:
            with db._connect() as conn:
                conn.execute("DELETE FROM baseline_atividade WHERE baseline_id IN "
                             "(SELECT id FROM baseline WHERE project_id=?)", (pid,))
                conn.execute("DELETE FROM baseline_ativa WHERE project_id=?", (pid,))
                conn.execute("DELETE FROM baseline WHERE project_id=?", (pid,))
                conn.execute("DELETE FROM dependencia WHERE project_id=?", (pid,))
                conn.execute("DELETE FROM atividade WHERE project_id=?", (pid,))
                conn.commit()
            result["cleaned"] = True
        except Exception as exc:
            result["cleanup_error"] = type(exc).__name__
            result["ok"] = False
        try:
            if db._turso_client is not None:
                db._turso_client.close()
        except Exception:
            pass
        db._turso_client = cached
        atividades.validar_eap_ref = previous_validator
        if prev_driver is None:
            os.environ.pop("TURSO_DRIVER", None)
        else:
            os.environ["TURSO_DRIVER"] = prev_driver
    return result
