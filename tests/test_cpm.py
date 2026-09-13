import pytest


def _rede_classica(db):
    """Exemplo clássico de livro-texto (Mattos, cap. 4):

        A(2) -> B(4) -> D(2)
        A(2) -> C(3) -> D(2)

    Caminho crítico esperado: A -> B -> D (duração total 8, folga 0).
    C tem folga de 1 dia (não é crítica).
    """
    a = db.criar_atividade({"eap_ref": "A", "nome": "A", "duracao_dias": 2})
    b = db.criar_atividade({"eap_ref": "B", "nome": "B", "duracao_dias": 4})
    c = db.criar_atividade({"eap_ref": "C", "nome": "C", "duracao_dias": 3})
    d = db.criar_atividade({"eap_ref": "D", "nome": "D", "duracao_dias": 2})
    db.criar_dependencia(a["id"], b["id"])
    db.criar_dependencia(a["id"], c["id"])
    db.criar_dependencia(b["id"], d["id"])
    db.criar_dependencia(c["id"], d["id"])
    return a, b, c, d


def test_caminho_critico_exemplo_classico(db):
    a, b, c, d = _rede_classica(db)
    resultado = db.calcular_caminho_critico(db.DEFAULT_PROJECT_ID)

    assert resultado["duracao_total_dias"] == 8.0

    por_id = {x["id"]: x for x in resultado["atividades"]}
    assert por_id[a["id"]]["es"] == 0 and por_id[a["id"]]["ef"] == 2
    assert por_id[b["id"]]["es"] == 2 and por_id[b["id"]]["ef"] == 6
    assert por_id[c["id"]]["es"] == 2 and por_id[c["id"]]["ef"] == 5
    assert por_id[d["id"]]["es"] == 6 and por_id[d["id"]]["ef"] == 8

    assert por_id[a["id"]]["folga_total"] == 0
    assert por_id[b["id"]]["folga_total"] == 0
    assert por_id[c["id"]]["folga_total"] == 1
    assert por_id[d["id"]]["folga_total"] == 0

    ids_criticos = {x["id"] for x in resultado["caminho_critico"]}
    assert ids_criticos == {a["id"], b["id"], d["id"]}


def test_caminho_critico_persiste_no_banco(db):
    a, b, c, d = _rede_classica(db)
    db.calcular_caminho_critico(db.DEFAULT_PROJECT_ID)
    atividade_persistida = db.buscar_atividade(c["id"])
    assert atividade_persistida["folga_total"] == 1
    assert atividade_persistida["critica"] == 0  # sqlite guarda bool como 0/1


def test_caminho_critico_sem_atividades_falha(db):
    with pytest.raises(ValueError, match="não tem atividades"):
        db.calcular_caminho_critico(db.DEFAULT_PROJECT_ID)


def test_caminho_critico_atividade_sem_duracao_falha(db):
    db.criar_atividade({"eap_ref": "1.1", "nome": "Sem duração"})
    with pytest.raises(ValueError, match="sem duração"):
        db.calcular_caminho_critico(db.DEFAULT_PROJECT_ID)


def test_caminho_critico_atividade_isolada(db):
    """Uma única atividade sem dependência é, trivialmente, o caminho crítico."""
    a = db.criar_atividade({"eap_ref": "1.1", "nome": "Isolada", "duracao_dias": 5})
    resultado = db.calcular_caminho_critico(db.DEFAULT_PROJECT_ID)
    assert resultado["duracao_total_dias"] == 5
    assert len(resultado["caminho_critico"]) == 1
    assert resultado["caminho_critico"][0]["id"] == a["id"]


def test_dependencia_tipo_ii_inicio_inicio(db):
    """B começa junto com A (II), não depois que A termina."""
    a = db.criar_atividade({"eap_ref": "A", "nome": "A", "duracao_dias": 5})
    b = db.criar_atividade({"eap_ref": "B", "nome": "B", "duracao_dias": 3})
    db.criar_dependencia(a["id"], b["id"], tipo="II")
    resultado = db.calcular_caminho_critico(db.DEFAULT_PROJECT_ID)
    por_id = {x["id"]: x for x in resultado["atividades"]}
    assert por_id[b["id"]]["es"] == 0  # começa junto com A, não em ef(A)=5
    assert resultado["duracao_total_dias"] == 5  # A ainda domina (5 > 3)


def test_dependencia_com_lag(db):
    a = db.criar_atividade({"eap_ref": "A", "nome": "A", "duracao_dias": 2})
    b = db.criar_atividade({"eap_ref": "B", "nome": "B", "duracao_dias": 2})
    db.criar_dependencia(a["id"], b["id"], tipo="TI", lag_dias=3)
    resultado = db.calcular_caminho_critico(db.DEFAULT_PROJECT_ID)
    por_id = {x["id"]: x for x in resultado["atividades"]}
    assert por_id[b["id"]]["es"] == 5  # ef(A)=2 + lag 3
