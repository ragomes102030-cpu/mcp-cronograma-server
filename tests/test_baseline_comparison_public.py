import pytest
from models.baseline_comparison import comparar_baseline_em_memoria


def test_desvios_e_novos_itens():
    baseline = [{"id": "A", "duracao_dias": 5, "data_fim_planejada": "2026-11-10"},
                {"id": "B", "duracao_dias": 3}]
    atual = [{"id": "A", "duracao_dias": 8, "data_fim_planejada": "2026-11-12"},
             {"id": "C", "duracao_dias": 2}]
    r = comparar_baseline_em_memoria(baseline, atual)
    linhas = {x["id"]: x for x in r["comparacao"]}
    assert linhas["A"]["desvio_duracao_dias"] == 3
    assert linhas["A"]["desvio_fim_dias"] == 2
    assert linhas["B"]["situacao"] == "REMOVIDA"
    assert linhas["C"]["situacao"] == "ADICIONADA"
    assert r["persistido"] is False


@pytest.mark.parametrize("baseline,atual", [
    ([], []),
    ([{"id": "A"}, {"id": "A"}], []),
    ([{"id": "A", "duracao_dias": -1}], [{"id": "A"}]),
    ([{"id": "A", "data_fim_planejada": "2026-02-30"}], [{"id": "A"}]),
])
def test_invalido_falha_fechado(baseline, atual):
    with pytest.raises(ValueError):
        comparar_baseline_em_memoria(baseline, atual)
