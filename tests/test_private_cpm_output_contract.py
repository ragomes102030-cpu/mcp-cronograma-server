"""Regression for private CPM tool output schema discovered in authenticated QA.

The engine returned 3 diagnostic fields not declared by CaminhoCriticoOutput,
making private calcular_caminho_critico raise an MCP unexpected exception.
These tests use isolated local SQLite and never access production.
"""
import pytest
from pydantic import ValidationError

from schemas import CaminhoCriticoOutput


def test_private_cpm_output_schema_accepts_real_engine_diagnostics(db):
    p = db.criar_atividade({"eap_ref":"QA-1","nome":"Preparacao","duracao_dias":2})
    q = db.criar_atividade({"eap_ref":"QA-2","nome":"Estrutura","duracao_dias":4})
    db.criar_dependencia(p["id"],q["id"],tipo="TI")
    actual = db.calcular_caminho_critico(db.DEFAULT_PROJECT_ID)
    output = CaminhoCriticoOutput.model_validate(actual).model_dump()
    assert output["duracao_total_dias"] == 6
    assert output["total_atividades"] == 2
    assert output["atividades_sem_vinculo"] == []
    assert output["rede_sem_dependencias"] is False
    assert "dias corridos" in output["premissa_temporal"]
    assert len(output["atividades"]) == 2
    assert len(output["caminho_critico"]) == 2


def test_private_cpm_schema_reports_unconnected_network(db):
    db.criar_atividade({"eap_ref":"QA-3","nome":"A","duracao_dias":3})
    db.criar_atividade({"eap_ref":"QA-4","nome":"B","duracao_dias":5})
    actual = db.calcular_caminho_critico(db.DEFAULT_PROJECT_ID)
    output = CaminhoCriticoOutput.model_validate(actual).model_dump()
    assert output["rede_sem_dependencias"] is True
    assert len(output["atividades_sem_vinculo"]) == 2


def test_private_cpm_schema_still_rejects_undeclared_keys():
    data = {
        "project_id":"qa","duracao_total_dias":1,
        "total_atividades":1, "caminho_critico":[], "atividades":[],
        "unknown_future_key":True,
    }
    with pytest.raises(ValidationError):
        CaminhoCriticoOutput.model_validate(data)
