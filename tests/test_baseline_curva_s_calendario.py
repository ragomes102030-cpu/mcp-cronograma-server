from datetime import date

import pytest


def test_salvar_e_comparar_baseline(db):
    a = db.criar_atividade({
        "eap_ref": "1.1", "nome": "A", "duracao_dias": 5,
        "data_fim_planejada": "2026-01-10",
    })
    bl = db.salvar_baseline(db.DEFAULT_PROJECT_ID, "Aprovada Rev 0")
    assert bl["total_atividades"] == 1

    db.atualizar_atividade(a["id"], {"duracao_dias": 8})
    comparacao = db.comparar_baseline(bl["id"])
    linha = comparacao["comparacao"][0]
    assert linha["duracao_baseline"] == 5
    assert linha["duracao_atual"] == 8
    assert linha["desvio_duracao_dias"] == 3


def test_salvar_baseline_sem_atividades_falha(db):
    with pytest.raises(ValueError, match="não tem atividades"):
        db.salvar_baseline(db.DEFAULT_PROJECT_ID, "Vazia")


def test_curva_s_requer_cpm_calculado(db):
    db.criar_atividade({"eap_ref": "1.1", "nome": "A", "duracao_dias": 5})
    with pytest.raises(ValueError, match="calcular_caminho_critico"):
        db.curva_s(db.DEFAULT_PROJECT_ID)


def test_curva_s_acumula_corretamente(db):
    a = db.criar_atividade({"eap_ref": "A", "nome": "A", "duracao_dias": 4})
    b = db.criar_atividade({"eap_ref": "B", "nome": "B", "duracao_dias": 6})
    db.criar_dependencia(a["id"], b["id"])
    db.calcular_caminho_critico(db.DEFAULT_PROJECT_ID)
    db.atualizar_atividade(a["id"], {"percentual_concluido": 100})
    db.atualizar_atividade(b["id"], {"percentual_concluido": 50})

    resultado = db.curva_s(db.DEFAULT_PROJECT_ID)
    pontos = {p["atividade_id"]: p for p in resultado["pontos"]}
    # peso total = 4 + 6 = 10. A pesa 40%, concluída 100% -> 40% realizado acumulado.
    assert pontos[a["id"]]["planejado_acumulado_pct"] == 40.0
    assert pontos[a["id"]]["realizado_acumulado_pct"] == 40.0
    # B pesa 60% a mais -> planejado acumulado 100%; realizado: 40% + 60%*0.5=30% = 70%
    assert pontos[b["id"]]["planejado_acumulado_pct"] == 100.0
    assert pontos[b["id"]]["realizado_acumulado_pct"] == 70.0


def test_somar_dias_uteis_pula_fim_de_semana(db):
    # 2026-01-05 é uma segunda-feira.
    inicio = date(2026, 1, 5)
    resultado = db.somar_dias_uteis(inicio, 5)
    # seg,ter,qua,qui,sex = 5 dias úteis -> cai na sexta 2026-01-09
    assert resultado == date(2026, 1, 9)


def test_somar_dias_uteis_com_feriado(db):
    inicio = date(2026, 1, 5)  # segunda
    feriados = {date(2026, 1, 6)}  # terça é feriado
    resultado = db.somar_dias_uteis(inicio, 3, feriados)
    # seg(1), pula ter(feriado), qua(2), qui(3) -> 2026-01-08
    assert resultado == date(2026, 1, 8)
