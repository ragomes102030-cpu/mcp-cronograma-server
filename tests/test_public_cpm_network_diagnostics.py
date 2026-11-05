from public_mcp import diagnosticar_rede_cpm


def _activities():
    return [{"id": "A", "duracao_dias": 2}, {"id": "B", "duracao_dias": 3}]


def _dep(a, b):
    return {"predecessora_id": a, "sucessora_id": b, "tipo": "TI", "lag_dias": 0}


def test_cycle_is_structured():
    result = diagnosticar_rede_cpm(_activities(), [_dep("A", "B"), _dep("B", "A")])
    assert not result["valid"]
    assert any(e["codigo"] == "CICLO" for e in result["erros"])
    assert result["persistido"] is False


def test_dangling_reference():
    result = diagnosticar_rede_cpm(_activities(), [_dep("A", "C")])
    assert any(e["codigo"] == "REFERENCIA_INEXISTENTE" for e in result["erros"])


def test_valid_network():
    result = diagnosticar_rede_cpm(_activities(), [_dep("A", "B")])
    assert result["valid"]
    assert result["atividades_sem_vinculo"] == []


def test_isolated_activity():
    result = diagnosticar_rede_cpm(_activities() + [{"id": "C", "duracao_dias": 1}], [_dep("A", "B")])
    assert result["valid"]
    assert result["atividades_sem_vinculo"] == ["C"]
