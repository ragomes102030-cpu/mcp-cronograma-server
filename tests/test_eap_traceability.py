"""Testes da integração de rastreabilidade atividade -> EAP."""
from __future__ import annotations

import pytest

from models import atividades


def test_criar_atividade_exige_validacao_eap(db, monkeypatch):
    chamadas = []

    def fake_validar(project_id, eap_ref):
        chamadas.append((project_id, eap_ref))
        return {"encontrado": True, "uid": "uid-1", "eap_id": "1.1"}

    monkeypatch.setattr(atividades, "validar_eap_ref", fake_validar)
    a = atividades.criar_atividade({
        "project_id": "OBRA-1",
        "eap_ref": "1.1",
        "nome": "Escavação",
        "duracao_dias": 3,
    })
    assert a["eap_ref"] == "1.1"
    assert chamadas == [("OBRA-1", "1.1")]


def test_criar_atividade_reprova_eap_inexistente(db, monkeypatch):
    def fake_validar(project_id, eap_ref):
        raise ValueError(
            f"eap_ref '{eap_ref}' não existe no projeto '{project_id}' no MCP-EAP."
        )

    monkeypatch.setattr(atividades, "validar_eap_ref", fake_validar)
    with pytest.raises(ValueError, match="não existe"):
        atividades.criar_atividade({
            "project_id": "OBRA-1",
            "eap_ref": "9.9",
            "nome": "Atividade órfã",
            "duracao_dias": 2,
        })
