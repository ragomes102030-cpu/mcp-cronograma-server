"""Critical path P3: validate ordered paths using known networks.

Never persist activities, baselines or actual construction data.
"""
from __future__ import annotations
from public_mcp import calcular_cpm_com_evidencia


def test_two_equal_critical_paths_are_distinct_and_ordered():
    r=calcular_cpm_com_evidencia(
        [{"id":"A","duracao_dias":2},
         {"id":"B","duracao_dias":2},
         {"id":"C","duracao_dias":2}],
        [{"predecessora_id":"A","sucessora_id":"B","tipo":"TI","lag_dias":0},
         {"predecessora_id":"A","sucessora_id":"C","tipo":"TI","lag_dias":0}])
    assert r["duracao_projeto_dias"] == 4
    assert sorted(r["caminhos_criticos"]) == [["A","B"],["A","C"]]
    assert set(r["caminho_critico"]) == {"A","B","C"}
    assert r["caminhos_criticos_truncados"] is False
    assert r["persistido"] is False


def test_one_critical_path_and_noncritical_branch():
    r=calcular_cpm_com_evidencia(
        [{"id":"A","duracao_dias":2},{"id":"B","duracao_dias":4},
         {"id":"C","duracao_dias":3},{"id":"D","duracao_dias":2}],
        [{"predecessora_id":"A","sucessora_id":"B","tipo":"TI"},
         {"predecessora_id":"A","sucessora_id":"C","tipo":"TI"},
         {"predecessora_id":"B","sucessora_id":"D","tipo":"TI"},
         {"predecessora_id":"C","sucessora_id":"D","tipo":"TI"}])
    assert r["duracao_projeto_dias"] == 8
    assert r["caminhos_criticos"] == [["A","B","D"]]
    assert set(r["caminho_critico"]) == {"A","B","D"}


def test_single_task_and_generalized_start_start():
    one=calcular_cpm_com_evidencia([{"id":"A","duracao_dias":3}],[])
    assert one["caminhos_criticos"] == [["A"]]
    many=calcular_cpm_com_evidencia(
        [{"id":"A","duracao_dias":5},{"id":"B","duracao_dias":3}],
        [{"predecessora_id":"A","sucessora_id":"B","tipo":"II","lag_dias":10}])
    assert many["duracao_projeto_dias"] == 13
    assert many["caminhos_criticos"] == [["A","B"]]


def test_unlinked_activity_is_not_invented_as_critical_link():
    r=calcular_cpm_com_evidencia(
        [{"id":"A","duracao_dias":2},{"id":"B","duracao_dias":1},
         {"id":"C","duracao_dias":5}],
        [{"predecessora_id":"A","sucessora_id":"B","tipo":"TI"}])
    assert r["duracao_projeto_dias"] == 5
    assert r["caminhos_criticos"] == [["C"]]
    assert r["atividades_sem_vinculo"] == ["C"]
