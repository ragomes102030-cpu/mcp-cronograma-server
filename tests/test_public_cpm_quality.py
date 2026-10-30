"""Folga livre validada independentemente da folga total."""
from public_mcp import calcular_cpm_com_evidencia


def _rede():
    atividades = [
        {"id": "A", "duracao_dias": 2},
        {"id": "B", "duracao_dias": 4},
        {"id": "C", "duracao_dias": 3},
        {"id": "D", "duracao_dias": 2},
    ]
    dependencias = [
        {"predecessora_id": "A", "sucessora_id": "B"},
        {"predecessora_id": "A", "sucessora_id": "C"},
        {"predecessora_id": "B", "sucessora_id": "D"},
        {"predecessora_id": "C", "sucessora_id": "D"},
    ]
    return atividades, dependencias


def test_folga_livre_e_total_em_rede_diamante():
    resultado = calcular_cpm_com_evidencia(*_rede())
    por_id = {a["id"]: a for a in resultado["atividades"]}
    assert resultado["duracao_projeto_dias"] == 8
    assert por_id["C"]["folga_total"] == 1
    assert por_id["C"]["folga_livre"] == 1
    assert por_id["B"]["folga_livre"] == 0
    assert por_id["A"]["folga_livre"] == 0
    assert por_id["D"]["folga_livre"] == 0
    assert resultado["atividades_sem_vinculo"] == []


def test_atividade_isolada_reportada_sem_inventar_dependencia():
    a = [{"id": "A", "duracao_dias": 2},
         {"id": "B", "duracao_dias": 1},
         {"id": "C", "duracao_dias": 5}]
    deps = [{"predecessora_id": "A", "sucessora_id": "B"}]
    r = calcular_cpm_com_evidencia(a, deps)
    por_id = {x["id"]: x for x in r["atividades"]}
    assert r["atividades_sem_vinculo"] == ["C"]
    assert por_id["B"]["folga_livre"] == 2
    assert por_id["A"]["folga_livre"] == 0


def test_folga_livre_com_dependencia_inicio_inicio():
    a = [{"id": "A", "duracao_dias": 5},
         {"id": "B", "duracao_dias": 3}]
    dep = [{"predecessora_id": "A", "sucessora_id": "B",
            "tipo": "II", "lag_dias": 0}]
    r = calcular_cpm_com_evidencia(a, dep)
    por_id = {x["id"]: x for x in r["atividades"]}
    assert por_id["A"]["folga_livre"] == 0
    assert por_id["B"]["folga_livre"] == 2
    assert r["duracao_projeto_dias"] == 5
