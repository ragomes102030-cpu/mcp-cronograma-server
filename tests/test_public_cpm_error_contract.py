"""Regressao: redes CPM invalidas devolvem diagnostico utilizavel ao cliente publico.

Todos os dados sao sinteticos, sem banco e sem alteracao de baseline.
"""
from public_mcp import calcular_cpm_com_evidencia


ATIVIDADES = [{"id": "A", "duracao_dias": 2}, {"id": "B", "duracao_dias": 3}]


def _dep(predecessora, sucessora):
    return {"predecessora_id": predecessora, "sucessora_id": sucessora, "tipo": "TI"}


def _assert_erro(resultado, codigo):
    assert resultado["valid"] is False
    assert resultado["persistido"] is False
    assert resultado["origem"] == "dados_da_chamada"
    assert any(erro["codigo"] == codigo for erro in resultado["erros"])
    assert resultado["erro"]


def test_ciclo_retorna_erro_estruturado_sem_gravar():
    resultado = calcular_cpm_com_evidencia(ATIVIDADES, [_dep("A", "B"), _dep("B", "A")])
    _assert_erro(resultado, "CICLO")


def test_referencia_inexistente_retorna_erro_estruturado():
    resultado = calcular_cpm_com_evidencia(ATIVIDADES, [_dep("A", "Z")])
    _assert_erro(resultado, "REFERENCIA_INEXISTENTE")


def test_rede_sem_vinculos_retorna_erro_estruturado():
    resultado = calcular_cpm_com_evidencia(ATIVIDADES, [])
    _assert_erro(resultado, "REDE_SEM_DEPENDENCIAS")


def test_rede_valida_continua_calculando():
    resultado = calcular_cpm_com_evidencia(ATIVIDADES, [_dep("A", "B")])
    assert resultado["valid"] is True
    assert resultado["duracao_projeto_dias"] == 5
    assert resultado["caminho_critico"] == ["A", "B"]
    assert resultado["persistido"] is False


def test_cpm_recusa_dependencia_explicitamente_nao_aprovada():
    dependencia = {**_dep("A", "B"), "status": "PROPOSTA_NAO_APROVADA"}

    resultado = calcular_cpm_com_evidencia(ATIVIDADES, [dependencia])

    assert resultado["valid"] is False
    assert resultado["persistido"] is False
    assert resultado["erro"] == "Dependencias sem aprovacao rastreavel; CPM recusado"
    assert any(erro["codigo"] == "DEPENDENCIA_NAO_APROVADA" for erro in resultado["erros"])


def test_cpm_recusa_aprovacao_sem_referencia_de_evidencia():
    dependencia = {**_dep("A", "B"), "status": "APROVADA"}

    resultado = calcular_cpm_com_evidencia(ATIVIDADES, [dependencia])

    assert resultado["valid"] is False
    assert resultado["persistido"] is False
    assert resultado["erro"] == "Dependencias sem aprovacao rastreavel; CPM recusado"
    assert any(erro["codigo"] == "EVIDENCIA_APROVACAO_AUSENTE" for erro in resultado["erros"])
