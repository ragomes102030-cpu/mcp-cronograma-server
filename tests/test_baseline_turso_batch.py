from models import baseline


def test_turso_usa_batch_atomico(db, monkeypatch):
    db.criar_atividade({"eap_ref": "1.1", "nome": "A", "duracao_dias": 5})
    chamadas = []
    class Client:
        def batch(self, statements):
            chamadas.append(statements)
    monkeypatch.setattr(baseline, "_TURSO_URL", "https://exemplo.turso.io")
    monkeypatch.setattr(baseline, "_get_turso_client", lambda: Client())
    r = db.salvar_baseline(db.DEFAULT_PROJECT_ID, "Rev 1")
    assert r["ativa"] is True
    assert len(chamadas) == 1
    assert len(chamadas[0]) == 3
    assert "baseline_ativa" in chamadas[0][-1]["sql"]


def test_turso_falha_nao_reporta_sucesso(db, monkeypatch):
    db.criar_atividade({"eap_ref": "1.1", "nome": "A", "duracao_dias": 5})
    class Client:
        def batch(self, statements):
            raise RuntimeError("falha transacional simulada")
    monkeypatch.setattr(baseline, "_TURSO_URL", "https://exemplo.turso.io")
    monkeypatch.setattr(baseline, "_get_turso_client", lambda: Client())
    import pytest
    with pytest.raises(RuntimeError, match="falha transacional"):
        db.salvar_baseline(db.DEFAULT_PROJECT_ID, "Rev 1")
