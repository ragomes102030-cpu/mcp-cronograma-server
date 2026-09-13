"""Curva S: acumulado de progresso (%) planejado x realizado ao longo do
cronograma. v1 pondera por duração de cada atividade (proxy de "peso" da
atividade no total); ponderar por custo real fica pra quando houver
integração com um MCP de orçamento — daria o mesmo formato de saída, só
trocando o peso de "duracao_dias" por "custo_previsto".
"""

from __future__ import annotations

from typing import Any

from .atividades import listar_atividades


def curva_s(project_id: str) -> dict[str, Any]:
    """Gera os pontos da curva S: para cada atividade (ordenada por EF),
    o percentual acumulado planejado (peso = duração) e o percentual
    acumulado realizado (peso = duração * percentual_concluido/100).
    """
    atividades = listar_atividades(project_id)
    if not atividades:
        raise ValueError(f"Projeto '{project_id}' não tem atividades cadastradas.")

    com_ef = [a for a in atividades if a.get("ef") is not None]
    if not com_ef:
        raise ValueError(
            "Nenhuma atividade tem EF calculado. Rode calcular_caminho_critico primeiro."
        )
    com_ef.sort(key=lambda a: a["ef"])

    peso_total = sum(a["duracao_dias"] or 0 for a in com_ef)
    if peso_total == 0:
        raise ValueError("Duração total das atividades é zero — nada para acumular.")

    acumulado_planejado = 0.0
    acumulado_realizado = 0.0
    pontos = []
    for a in com_ef:
        peso = a["duracao_dias"] or 0
        pct_concluido = a.get("percentual_concluido") or 0
        acumulado_planejado += peso
        acumulado_realizado += peso * (pct_concluido / 100.0)
        pontos.append({
            "atividade_id": a["id"],
            "nome": a["nome"],
            "ef": a["ef"],
            "planejado_acumulado_pct": round(100 * acumulado_planejado / peso_total, 4),
            "realizado_acumulado_pct": round(100 * acumulado_realizado / peso_total, 4),
        })

    return {
        "project_id": project_id,
        "peso_usado": "duracao_dias (dias de trabalho da atividade)",
        "pontos": pontos,
    }
