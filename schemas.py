"""Schemas Pydantic de saída das tools MCP. Erros usam ErroOutput uniforme."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class ErroOutput(BaseModel):
    erro: str
    model_config = ConfigDict(extra="forbid")


class AtividadeOutput(BaseModel):
    id: str
    project_id: str
    eap_ref: str
    nome: str
    duracao_dias: Optional[float] = None
    duracao_otimista: Optional[float] = None
    duracao_provavel: Optional[float] = None
    duracao_pessimista: Optional[float] = None
    percentual_concluido: float = 0
    data_inicio_planejada: Optional[str] = None
    data_fim_planejada: Optional[str] = None
    data_inicio_real: Optional[str] = None
    data_fim_real: Optional[str] = None
    es: Optional[float] = None
    ef: Optional[float] = None
    ls: Optional[float] = None
    lf: Optional[float] = None
    folga_total: Optional[float] = None
    folga_livre: Optional[float] = None
    critica: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class DependenciaOutput(BaseModel):
    id: str
    project_id: str
    predecessora_id: str
    sucessora_id: str
    tipo: str
    lag_dias: float = 0
    created_at: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class CaminhoCriticoOutput(BaseModel):
    project_id: str
    duracao_total_dias: float
    total_atividades: int
    caminho_critico: list[dict[str, Any]]
    atividades: list[dict[str, Any]]

    model_config = ConfigDict(extra="forbid")
