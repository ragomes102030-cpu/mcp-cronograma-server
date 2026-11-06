"""Stress stateless de redes grandes e compatibilidade do contrato da Plataforma Obras."""
from __future__ import annotations

import pytest
from public_mcp import (
    calcular_cpm_com_evidencia, calcular_cpm_com_calendario,
    comparar_baseline_sem_persistencia, diagnosticar_rede_cpm,
)


def rede(qtd=2000, vinculos=10000):
    assert 1 <= qtd <= 2001
    atividades = [{"id": f"A{i:04d}", "duracao_dias": 1} for i in range(qtd)]
    dep = []
    for gap in range(1, qtd):
        for i in range(qtd - gap):
            if len(dep) == vinculos:
                return atividades, dep
            dep.append({
                "predecessora_id": atividades[i]["id"],
                "sucessora_id": atividades[i + gap]["id"],
                "tipo": "FS", "lag_dias": 0,
            })
    return atividades, dep


def test_cpm_2000_atividades_10000_vinculos():
    atividades, dependencias = rede()
    assert len(dependencias) == 10000
    r = calcular_cpm_com_evidencia(atividades, dependencias)
    assert r["valid"] is True
    assert r["persistido"] is False
    assert len(r["atividades"]) == 2000
    assert r["duracao_projeto_dias"] == 2000
    assert len(r["caminho_critico"]) == 2000
    assert len(r["caminhos_criticos"]) == 1
    assert len(r["caminhos_criticos"][0]) == 2000
    assert r["caminhos_criticos_truncados"] is False


def test_diagnostico_2000_atividades_sem_rede_fragmentada():
    a, d = rede()
    r = diagnosticar_rede_cpm(a, d)
    assert r["valid"] is True
    assert r["atividades_sem_vinculo"] == []
    assert r["persistido"] is False


@pytest.mark.parametrize("sigla,legado", [
    ("FS", "TI"), ("SS", "II"), ("FF", "TT"), ("SF", "IT")
])
def test_siglas_usadas_pela_plataforma_equivalem_as_do_mcp(sigla, legado):
    a = [{"id": "A", "duracao_dias": 3}, {"id": "B", "duracao_dias": 2}]
    def calcular(tipo):
        return calcular_cpm_com_evidencia(a, [
            {"predecessora_id": "A", "sucessora_id": "B", "tipo": tipo, "lag_dias": 1}
        ])
    x = calcular(sigla)
    y = calcular(legado)
    assert x["valid"] and y["valid"]
    assert x["duracao_projeto_dias"] == y["duracao_projeto_dias"]
    assert x["atividades"] == y["atividades"]


def test_calendario_com_FS_da_plataforma():
    r = calcular_cpm_com_calendario(
        [{"id": "A", "duracao_dias": 2}, {"id": "B", "duracao_dias": 2}],
        [{"predecessora_id": "A", "sucessora_id": "B", "tipo": "FS", "lag_dias": 0}],
        "2026-11-09",
        {"modo": "uteis", "dias_semana": [0, 1, 2, 3, 4], "feriados": []},
    )
    assert r["valid"] is True
    assert r["duracao_projeto_dias"] == 4
    assert r["data_fim_projeto_exclusiva"] == "2026-11-13"
    assert r["persistido"] is False


def test_cpm_2001_atividades_e_10001_vinculos_rejeitados():
    a, d = rede()
    with pytest.raises(ValueError, match="2000"):
        calcular_cpm_com_evidencia(a + [{"id": "X", "duracao_dias": 1}], d)
    with pytest.raises(ValueError, match="10000"):
        calcular_cpm_com_evidencia(a, d + [d[0]])


def test_comparacao_baseline_2000_sem_escrita():
    antigos = [{"id": f"A{i}", "duracao_dias": 3, "data_fim_planejada": "2027-05-01"} for i in range(2000)]
    novos = [{**a, "duracao_dias": 4} for a in antigos]
    r = comparar_baseline_sem_persistencia(antigos, novos)
    assert r["valid"] is True
    assert r["total_baseline"] == 2000
    assert len(r["comparacao"]) == 2000
    assert all(x["desvio_duracao_dias"] == 1 for x in r["comparacao"])
    assert r["persistido"] is False
    with pytest.raises(ValueError, match="2000"):
        comparar_baseline_sem_persistencia(antigos + [dict(antigos[0], id="A2000")], novos)
