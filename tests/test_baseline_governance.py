import pytest


def test_uma_ativa_e_historico_preservado(db):
    db.criar_atividade({"eap_ref": "1.1", "nome": "A", "duracao_dias": 5})
    primeira = db.salvar_baseline(db.DEFAULT_PROJECT_ID, "Rev 0")
    segunda = db.salvar_baseline(db.DEFAULT_PROJECT_ID, "Rev 1")
    itens = db.listar_baselines(db.DEFAULT_PROJECT_ID)
    assert len(itens) == 2
    assert [x["id"] for x in itens if x["ativa"]] == [segunda["id"]]
    assert any(x["id"] == primeira["id"] and not x["ativa"] for x in itens)
    assert db.comparar_baseline(primeira["id"])["baseline"]["id"] == primeira["id"]


def test_rollback_sem_snapshot_parcial(db, monkeypatch):
    db.criar_atividade({"eap_ref": "1.1", "nome": "A", "duracao_dias": 5})
    primeira = db.salvar_baseline(db.DEFAULT_PROJECT_ID, "Rev 0")
    from models import baseline
    monkeypatch.setattr(baseline, "_gerar_id", lambda _: primeira["id"])
    with pytest.raises(Exception):
        db.salvar_baseline(db.DEFAULT_PROJECT_ID, "Falha")
    itens = db.listar_baselines(db.DEFAULT_PROJECT_ID)
    assert len(itens) == 1 and itens[0]["ativa"]
