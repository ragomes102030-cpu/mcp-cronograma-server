from public_mcp import diagnosticar_rede_cpm


def _activities():
    return [{"id": "A", "duracao_dias": 2}, {"id": "B", "duracao_dias": 3}]


def _dep(a, b):
    return {"predecessora_id": a, "sucessora_id": b, "tipo": "TI", "lag_dias": 0}


def _dep_with_status(a, b, status):
    return {**_dep(a, b), "status": status}


def test_cycle_is_structured():
    result = diagnosticar_rede_cpm(_activities(), [_dep("A", "B"), _dep("B", "A")])
    assert not result["valid"]
    assert any(e["codigo"] == "CICLO" for e in result["erros"])
    assert result["topologia_pronta_para_cpm"] is False
    assert result["persistido"] is False


def test_dangling_reference():
    result = diagnosticar_rede_cpm(_activities(), [_dep("A", "C")])
    assert any(e["codigo"] == "REFERENCIA_INEXISTENTE" for e in result["erros"])
    assert result["topologia_pronta_para_cpm"] is False


def test_valid_network():
    result = diagnosticar_rede_cpm(_activities(), [_dep("A", "B")])
    assert result["valid"]
    assert result["atividades_sem_vinculo"] == []
    assert result["topologia_pronta_para_cpm"] is True
    assert result["pronto_para_cpm"] is True


def test_isolated_activity():
    result = diagnosticar_rede_cpm(_activities() + [{"id": "C", "duracao_dias": 1}], [_dep("A", "B")])
    assert result["valid"]
    assert result["atividades_sem_vinculo"] == ["C"]
    assert result["pronto_para_cpm"] is False
    assert result["topologia_pronta_para_cpm"] is False


def test_proposed_relation_is_structurally_valid_but_not_cpm_ready():
    result = diagnosticar_rede_cpm(
        _activities(), [_dep_with_status("A", "B", "PROPOSTA_NAO_APROVADA")]
    )

    assert result["valid"] is True
    assert result["pronto_para_cpm"] is False
    assert result["dependencias_aprovadas"] == 0
    assert result["dependencias_pendentes_aprovacao"] == 1


def test_diagnostic_reports_missing_duration_as_not_cpm_ready():
    result = diagnosticar_rede_cpm(
        [{"id": "A", "duracao_dias": 2}, {"id": "B", "duracao_dias": None}],
        [_dep("A", "B")],
    )

    assert result["valid"] is True
    assert result["pronto_para_cpm"] is False
    assert result["atividades_sem_duracao"] == ["B"]


def test_approval_status_without_evidence_does_not_release_relation():
    result = diagnosticar_rede_cpm(
        _activities(), [_dep_with_status("A", "B", "APROVADA")]
    )

    assert result["valid"] is True
    assert result["pronto_para_cpm"] is False
    assert result["dependencias_aprovadas"] == 0
    assert result["dependencias_sem_evidencia_aprovacao"] == 1


def test_approval_status_with_evidence_makes_connected_network_ready():
    dependency = {
        **_dep_with_status("A", "B", "APROVADA"),
        "evidencia_aprovacao": "ATA-PLANEJAMENTO-001, item 4",
    }

    result = diagnosticar_rede_cpm(_activities(), [dependency])

    assert result["valid"] is True
    assert result["pronto_para_cpm"] is True
    assert result["dependencias_aprovadas"] == 1
