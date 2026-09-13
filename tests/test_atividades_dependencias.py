import pytest


def test_criar_atividade_basica(db):
    a = db.criar_atividade({"eap_ref": "1.1", "nome": "Fundação", "duracao_dias": 5})
    assert a["nome"] == "Fundação"
    assert a["duracao_dias"] == 5
    assert a["percentual_concluido"] == 0


def test_criar_atividade_sem_eap_ref_ou_nome_falha(db):
    with pytest.raises(ValueError, match="eap_ref"):
        db.criar_atividade({"nome": "X"})
    with pytest.raises(ValueError, match="nome"):
        db.criar_atividade({"eap_ref": "1.1"})


def test_duracao_pert_calculada_automaticamente(db):
    a = db.criar_atividade({
        "eap_ref": "1.1", "nome": "Escavação",
        "duracao_otimista": 2, "duracao_provavel": 4, "duracao_pessimista": 12,
    })
    # (2 + 4*4 + 12) / 6 = 30/6 = 5.0
    assert a["duracao_dias"] == 5.0


def test_atualizar_atividade_percentual_fora_do_intervalo(db):
    a = db.criar_atividade({"eap_ref": "1.1", "nome": "X", "duracao_dias": 3})
    with pytest.raises(ValueError, match="0 e 100"):
        db.atualizar_atividade(a["id"], {"percentual_concluido": 150})


def test_deletar_atividade_com_dependencia_falha(db):
    a1 = db.criar_atividade({"eap_ref": "1.1", "nome": "A", "duracao_dias": 2})
    a2 = db.criar_atividade({"eap_ref": "1.2", "nome": "B", "duracao_dias": 3})
    db.criar_dependencia(a1["id"], a2["id"])
    with pytest.raises(ValueError, match="dependência"):
        db.deletar_atividade(a1["id"])


def test_criar_dependencia_tipo_invalido(db):
    a1 = db.criar_atividade({"eap_ref": "1.1", "nome": "A", "duracao_dias": 2})
    a2 = db.criar_atividade({"eap_ref": "1.2", "nome": "B", "duracao_dias": 3})
    with pytest.raises(ValueError, match="inválido"):
        db.criar_dependencia(a1["id"], a2["id"], tipo="XX")


def test_criar_dependencia_autodependencia_falha(db):
    a1 = db.criar_atividade({"eap_ref": "1.1", "nome": "A", "duracao_dias": 2})
    with pytest.raises(ValueError, match="ela mesma"):
        db.criar_dependencia(a1["id"], a1["id"])


def test_criar_dependencia_ciclo_e_rejeitado(db):
    a = db.criar_atividade({"eap_ref": "1", "nome": "A", "duracao_dias": 1})
    b = db.criar_atividade({"eap_ref": "2", "nome": "B", "duracao_dias": 1})
    c = db.criar_atividade({"eap_ref": "3", "nome": "C", "duracao_dias": 1})
    db.criar_dependencia(a["id"], b["id"])
    db.criar_dependencia(b["id"], c["id"])
    with pytest.raises(ValueError, match="ciclo"):
        db.criar_dependencia(c["id"], a["id"])


def test_criar_dependencia_duplicada_falha(db):
    a1 = db.criar_atividade({"eap_ref": "1.1", "nome": "A", "duracao_dias": 2})
    a2 = db.criar_atividade({"eap_ref": "1.2", "nome": "B", "duracao_dias": 3})
    db.criar_dependencia(a1["id"], a2["id"])
    with pytest.raises(ValueError, match="já existe"):
        db.criar_dependencia(a1["id"], a2["id"])


def test_validar_dependencias_rede_valida(db):
    a1 = db.criar_atividade({"eap_ref": "1.1", "nome": "A", "duracao_dias": 2})
    a2 = db.criar_atividade({"eap_ref": "1.2", "nome": "B", "duracao_dias": 3})
    db.criar_dependencia(a1["id"], a2["id"])
    resultado = db.validar_dependencias()
    assert resultado["resumo"]["rede_valida"] is True
    assert resultado["resumo"]["total_dependencias"] == 1


def test_listar_atividades_paginacao(db):
    for i in range(5):
        db.criar_atividade({"eap_ref": f"1.{i}", "nome": f"Item {i}", "duracao_dias": 1})
    pagina = db.listar_atividades(limit=2, offset=0)
    assert len(pagina) == 2
    assert db.contar_atividades() == 5
