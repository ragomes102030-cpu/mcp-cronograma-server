"""Baseline integrity regression using isolated local SQLite only."""
import pytest


def test_baseline_revision_preserves_original_snapshot(db):
    first_activity = db.criar_atividade({"eap_ref": "1.1", "nome": "Fundacao", "duracao_dias": 5})
    first = db.salvar_baseline(db.DEFAULT_PROJECT_ID, "Contratual")
    db.criar_atividade({"eap_ref": "1.2", "nome": "Estrutura", "duracao_dias": 8})
    second = db.salvar_baseline(db.DEFAULT_PROJECT_ID, "Replanejamento")
    baselines = db.listar_baselines(db.DEFAULT_PROJECT_ID)
    assert len(baselines) == 2
    assert sum(bool(item["ativa"]) for item in baselines) == 1
    assert next(item for item in baselines if item["ativa"])["id"] == second["id"]
    old = db.comparar_baseline(first["id"])
    new = db.comparar_baseline(second["id"])
    assert old["baseline"]["id"] == first["id"]
    assert new["baseline"]["id"] == second["id"]


def test_failed_new_revision_does_not_deactivate_active(db, monkeypatch):
    db.criar_atividade({"eap_ref": "1.1", "nome": "Fundacao", "duracao_dias": 5})
    active = db.salvar_baseline(db.DEFAULT_PROJECT_ID, "Contratual")
    from models import baseline
    monkeypatch.setattr(baseline, "_gerar_id", lambda _: active["id"])
    with pytest.raises(Exception):
        db.salvar_baseline(db.DEFAULT_PROJECT_ID, "Revisao falha")
    baselines = db.listar_baselines(db.DEFAULT_PROJECT_ID)
    assert len(baselines) == 1
    assert baselines[0]["id"] == active["id"]
    assert baselines[0]["ativa"] is True
