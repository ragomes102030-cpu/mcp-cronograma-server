"""Cálculo do caminho crítico (CPM) — Cap. 4 do Mattos.

Implementa o algoritmo clássico em duas passadas sobre a rede de atividades:

  1. Forward pass (cedo): ES (early start) e EF (early finish) de cada
     atividade, percorrendo a rede em ordem topológica a partir das
     atividades sem predecessora.
  2. Backward pass (tarde): LS (late start) e LF (late finish), percorrendo
     a rede na ordem topológica inversa a partir das atividades sem
     sucessora, ancorado no maior EF da rede (prazo total do projeto).

Folga total = LS - ES (quanto a atividade pode atrasar sem atrasar o
projeto). Folga livre = quanto pode atrasar sem atrasar a sucessora mais
cedo (mais restritiva). Atividade é crítica quando folga total == 0.

Suporta as 4 relações (TI/II/TT/IT) com lag, mas o cálculo é feito em
"unidades de duração" (dias corridos a partir de um marco zero), não em
datas de calendário — converter pra datas reais (pulando fins de semana e
feriados) é responsabilidade de ``calendario.py``/``gerar_cronograma``.
"""

from __future__ import annotations

from typing import Any

from .atividades import listar_atividades, salvar_resultado_cpm
from .dependencias import listar_dependencias


class RedeInvalidaError(ValueError):
    """Rede com ciclo ou dependência órfã — CPM não pode ser calculado."""


def _ordem_topologica(
    nos: list[str], arestas: list[tuple[str, str]]
) -> list[str]:
    """Kahn's algorithm. Levanta RedeInvalidaError se houver ciclo."""
    grau_entrada = {n: 0 for n in nos}
    adjacencia: dict[str, list[str]] = {n: [] for n in nos}
    for pred, suc in arestas:
        if pred not in grau_entrada or suc not in grau_entrada:
            continue  # dependência órfã — ignorada aqui, reportada por validar_dependencias
        adjacencia[pred].append(suc)
        grau_entrada[suc] += 1

    fila = [n for n in nos if grau_entrada[n] == 0]
    ordem: list[str] = []
    while fila:
        atual = fila.pop(0)
        ordem.append(atual)
        for viz in adjacencia[atual]:
            grau_entrada[viz] -= 1
            if grau_entrada[viz] == 0:
                fila.append(viz)

    if len(ordem) != len(nos):
        restantes = set(nos) - set(ordem)
        raise RedeInvalidaError(
            f"A rede tem um ciclo envolvendo: {', '.join(sorted(restantes))}. "
            "Rode validar_dependencias para localizar exatamente onde."
        )
    return ordem


def calcular_caminho_critico(project_id: str) -> dict[str, Any]:
    """Calcula ES/EF/LS/LF/folgas de todas as atividades do projeto e persiste.

    Retorna um resumo com a duração total do projeto e a lista de
    atividades no caminho crítico (folga total == 0), na ordem da rede.
    """
    atividades = listar_atividades(project_id)
    if not atividades:
        raise ValueError(f"Projeto '{project_id}' não tem atividades cadastradas.")

    sem_duracao = [a["id"] for a in atividades if a.get("duracao_dias") is None]
    if sem_duracao:
        raise ValueError(
            f"{len(sem_duracao)} atividade(s) sem duração definida "
            f"(nem duracao_dias, nem PERT completo): {', '.join(sem_duracao[:5])}"
            + ("..." if len(sem_duracao) > 5 else "")
        )

    deps = listar_dependencias(project_id)
    ids = [a["id"] for a in atividades]
    duracao = {a["id"]: float(a["duracao_dias"]) for a in atividades}
    arestas = [(d["predecessora_id"], d["sucessora_id"]) for d in deps]
    dep_por_par = {(d["predecessora_id"], d["sucessora_id"]): d for d in deps}

    ordem = _ordem_topologica(ids, arestas)

    predecessoras: dict[str, list[str]] = {n: [] for n in ids}
    sucessoras: dict[str, list[str]] = {n: [] for n in ids}
    for pred, suc in arestas:
        predecessoras[suc].append(pred)
        sucessoras[pred].append(suc)

    es: dict[str, float] = {}
    ef: dict[str, float] = {}

    # ── Forward pass ────────────────────────────────────────────────────
    for atual in ordem:
        candidatos_es = [0.0]
        for pred in predecessoras[atual]:
            dep = dep_por_par[(pred, atual)]
            lag = dep["lag_dias"] or 0
            tipo = dep["tipo"]
            if tipo == "TI":       # sucessora começa após predecessora terminar
                candidatos_es.append(ef[pred] + lag)
            elif tipo == "II":     # sucessora começa quando predecessora começa
                candidatos_es.append(es[pred] + lag)
            elif tipo == "TT":     # sucessora termina quando predecessora termina
                candidatos_es.append(ef[pred] + lag - duracao[atual])
            elif tipo == "IT":     # sucessora termina quando predecessora começa
                candidatos_es.append(es[pred] + lag - duracao[atual])
        es[atual] = max(candidatos_es)
        ef[atual] = es[atual] + duracao[atual]

    duracao_total_projeto = max(ef.values()) if ef else 0.0

    # ── Backward pass ───────────────────────────────────────────────────
    lf: dict[str, float] = {}
    ls: dict[str, float] = {}
    for atual in reversed(ordem):
        if not sucessoras[atual]:
            lf[atual] = duracao_total_projeto
        else:
            candidatos_lf = []
            for suc in sucessoras[atual]:
                dep = dep_por_par[(atual, suc)]
                lag = dep["lag_dias"] or 0
                tipo = dep["tipo"]
                if tipo == "TI":
                    candidatos_lf.append(ls[suc] - lag)
                elif tipo == "II":
                    candidatos_lf.append(ls[suc] - lag + duracao[atual])
                elif tipo == "TT":
                    candidatos_lf.append(lf[suc] - lag)
                elif tipo == "IT":
                    candidatos_lf.append(lf[suc] - lag + duracao[atual])
            lf[atual] = min(candidatos_lf) if candidatos_lf else duracao_total_projeto
        ls[atual] = lf[atual] - duracao[atual]

    # ── Folgas ──────────────────────────────────────────────────────────
    resultado_por_atividade: dict[str, dict[str, Any]] = {}
    for atual in ids:
        folga_total = round(ls[atual] - es[atual], 6)
        if sucessoras[atual]:
            folga_livre = round(
                min(es[suc] for suc in sucessoras[atual]) - ef[atual], 6
            )
        else:
            folga_livre = folga_total
        critica = abs(folga_total) < 1e-9

        campos_cpm = {
            "es": round(es[atual], 6), "ef": round(ef[atual], 6),
            "ls": round(ls[atual], 6), "lf": round(lf[atual], 6),
            "folga_total": folga_total, "folga_livre": max(folga_livre, 0.0),
            "critica": critica,
        }
        salvar_resultado_cpm(atual, campos_cpm)
        resultado_por_atividade[atual] = campos_cpm

    caminho_critico = [a for a in ordem if resultado_por_atividade[a]["critica"]]
    nomes = {a["id"]: a["nome"] for a in atividades}

    return {
        "project_id": project_id,
        "duracao_total_dias": round(duracao_total_projeto, 6),
        "total_atividades": len(ids),
        "caminho_critico": [
            {"id": a, "nome": nomes[a], **resultado_por_atividade[a]}
            for a in caminho_critico
        ],
        "atividades": [
            {"id": a, "nome": nomes[a], **resultado_por_atividade[a]}
            for a in ordem
        ],
    }
