"""Comparacao de baseline em memoria, sem banco ou alteracao de snapshots."""
from __future__ import annotations

import math
from datetime import date


def _indexar(itens: list[dict], rotulo: str) -> dict[str, dict]:
    if not isinstance(itens, list) or len(itens) > 500:
        raise ValueError(f"{rotulo}: lista invalida ou maior que 500")
    saida = {}
    for item in itens:
        if not isinstance(item, dict):
            raise ValueError(f"{rotulo}: atividade invalida")
        ident = str(item.get("id") or "").strip()
        if not ident or ident in saida:
            raise ValueError(f"{rotulo}: id vazio ou duplicado")
        saida[ident] = item
    return saida


def _duracao(item: dict) -> float | None:
    valor = item.get("duracao_dias")
    if valor is None:
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise ValueError("duracao_dias invalida")
    if not math.isfinite(numero) or numero <= 0:
        raise ValueError("duracao_dias deve ser positiva e finita")
    return numero


def _data(item: dict, chave: str) -> date | None:
    valor = item.get(chave)
    if valor is None:
        return None
    if not isinstance(valor, str):
        raise ValueError(f"{chave} deve ser data ISO")
    try:
        return date.fromisoformat(valor)
    except ValueError:
        raise ValueError(f"{chave} deve ser data ISO valida")


def comparar_baseline_em_memoria(baseline: list[dict], atual: list[dict]) -> dict:
    """Desvios positivos indicam atraso/aumento; datas em dias corridos."""
    antes = _indexar(baseline, "baseline")
    agora = _indexar(atual, "atual")
    if not antes:
        raise ValueError("baseline vazia")
    linhas = []
    for ident, original in antes.items():
        if ident not in agora:
            linhas.append({"id": ident, "situacao": "REMOVIDA", "desvio_duracao_dias": None, "desvio_fim_dias": None})
            continue
        corrente = agora[ident]
        d0, d1 = _duracao(original), _duracao(corrente)
        f0, f1 = _data(original, "data_fim_planejada"), _data(corrente, "data_fim_planejada")
        linhas.append({"id": ident, "situacao": "EXISTENTE",
                       "desvio_duracao_dias": round(d1-d0, 6) if d0 is not None and d1 is not None else None,
                       "desvio_fim_dias": (f1-f0).days if f0 is not None and f1 is not None else None})
    for ident in agora:
        if ident not in antes:
            linhas.append({"id": ident, "situacao": "ADICIONADA", "desvio_duracao_dias": None, "desvio_fim_dias": None})
    return {"valid": True, "comparacao": linhas, "total_baseline": len(antes),
            "total_atual": len(agora), "persistido": False,
            "premissa": "datas ISO; desvio de termino em dias corridos; sem calendario de trabalho"}
