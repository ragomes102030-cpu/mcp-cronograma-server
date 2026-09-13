"""Camada de dados do mcp-cronograma-server (PERT/CPM).

Módulos: db (schema/conexão), atividades, dependencias, cpm (caminho
crítico), calendario (datas reais), baseline (previsto x realizado),
curva_s, idempotencia.
"""

from __future__ import annotations

from .atividades import (
    atualizar_atividade,
    buscar_atividade,
    contar_atividades,
    criar_atividade,
    deletar_atividade,
    duracao_esperada_pert,
    desvio_padrao_pert,
    listar_atividades,
)
from .baseline import comparar_baseline, listar_baselines, salvar_baseline
from .calendario import gerar_datas, somar_dias_uteis
from .cpm import RedeInvalidaError, calcular_caminho_critico
from .curva_s import curva_s
from .db import DB_PATH, DEFAULT_PROJECT_ID, TIPOS_DEPENDENCIA_VALIDOS, init_db
from .dependencias import (
    criar_dependencia,
    buscar_dependencia,
    deletar_dependencia,
    listar_dependencias,
    validar_dependencias,
)
from .idempotencia import salvar_idempotencia, verificar_idempotencia

__all__ = [
    "atualizar_atividade", "buscar_atividade", "contar_atividades", "criar_atividade",
    "deletar_atividade", "duracao_esperada_pert", "desvio_padrao_pert", "listar_atividades",
    "comparar_baseline", "listar_baselines", "salvar_baseline",
    "gerar_datas", "somar_dias_uteis",
    "RedeInvalidaError", "calcular_caminho_critico",
    "curva_s",
    "DB_PATH", "DEFAULT_PROJECT_ID", "TIPOS_DEPENDENCIA_VALIDOS", "init_db",
    "criar_dependencia", "buscar_dependencia", "deletar_dependencia",
    "listar_dependencias", "validar_dependencias",
    "salvar_idempotencia", "verificar_idempotencia",
]
