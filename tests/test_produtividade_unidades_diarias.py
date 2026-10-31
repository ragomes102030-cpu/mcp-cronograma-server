"""Regressao: produtividade por dia aceita unidade/dia sem conversao silenciosa."""
import pytest
from public_mcp import calcular_duracao_com_evidencia


def test_produtividade_diaria_explicita():
    r = calcular_duracao_com_evidencia(120, 20, "m²", "m²/dia", "cenario ficticio")
    assert r["duracaoDias"] == 6
    assert r["persistido"] is False


def test_formato_legado_preservado():
    assert calcular_duracao_com_evidencia(120, 20, "m²", "m²")["duracaoDias"] == 6


@pytest.mark.parametrize("taxa", ["m³/dia", "m²/h", "m²/semana", "", "m²/dia/dia"])
def test_unidades_incompativeis_rejeitadas(taxa):
    with pytest.raises(ValueError, match="Unidades nao compativeis"):
        calcular_duracao_com_evidencia(120, 20, "m²", taxa)
