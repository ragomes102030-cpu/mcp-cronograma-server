"""Linha de base (baseline): snapshot congelado do cronograma aprovado, pra
comparar contra o realizado depois (desvio de prazo, insumo da curva S)."""

from __future__ import annotations

from typing import Any

from .atividades import listar_atividades
from .db import DEFAULT_PROJECT_ID, _connect, _gerar_id, _to_dict, _to_list


def salvar_baseline(project_id: str, nome: str) -> dict[str, Any]:
    """Congela data_inicio/fim_planejada e duração de todas as atividades
    do projeto no momento da chamada."""
    atividades = listar_atividades(project_id)
    if not atividades:
        raise ValueError(f"Projeto '{project_id}' não tem atividades para congelar.")
    # Valida que todas as atividades têm duração antes de congelar
    sem_duracao = [a["id"] for a in atividades if a.get("duracao_dias") is None]
    if sem_duracao:
        raise ValueError(
            f"Não é possível salvar baseline: {len(sem_duracao)} atividade(s) "
            f"sem duração definida (nem duracao_dias, nem PERT completo): "
            f"{', '.join(sem_duracao[:5])}"
            + ("..." if len(sem_duracao) > 5 else "") +
            f". Adicione duração ou rode calcular_caminho_critico antes de salvar."
        )
    bid = _gerar_id("bl")
    with _connect() as conn:
        conn.execute(
            "INSERT INTO baseline (id, project_id, nome) VALUES (?, ?, ?)",
            (bid, project_id, nome),
        )
        for a in atividades:
            conn.execute(
                """
                INSERT INTO baseline_atividade
                    (baseline_id, atividade_id, data_inicio_planejada,
                     data_fim_planejada, duracao_dias)
                VALUES (?, ?, ?, ?, ?)
                """,
                (bid, a["id"], a.get("data_inicio_planejada"),
                 a.get("data_fim_planejada"), a.get("duracao_dias")),
            )
        conn.commit()
    return {"id": bid, "project_id": project_id, "nome": nome, "total_atividades": len(atividades)}


def listar_baselines(project_id: str | None = None) -> list[dict[str, Any]]:
    pid = project_id or DEFAULT_PROJECT_ID
    with _connect() as conn:
        cursor = conn.execute(
            "SELECT * FROM baseline WHERE project_id = ? ORDER BY criado_em", (pid,)
        )
    return _to_list(cursor.fetchall())


def comparar_baseline(baseline_id: str) -> dict[str, Any]:
    """Compara a baseline congelada contra o estado atual das atividades.

    ``desvio_dias`` positivo = atrasou em relação ao planejado na baseline.
    """
    with _connect() as conn:
        bl = _to_dict(conn.execute(
            "SELECT * FROM baseline WHERE id = ?", (baseline_id,)
        ).fetchone())
        if bl is None:
            raise ValueError(f"Baseline '{baseline_id}' não encontrada.")
        congelados = _to_list(conn.execute(
            "SELECT * FROM baseline_atividade WHERE baseline_id = ?", (baseline_id,)
        ).fetchall())

    comparacao = []
    with _connect() as conn:
        for c in congelados:
            atual = _to_dict(conn.execute(
                "SELECT * FROM atividade WHERE id = ?", (c["atividade_id"],)
            ).fetchone())
            if atual is None:
                comparacao.append({
                    "atividade_id": c["atividade_id"], "situacao": "DELETADA_DEPOIS_DA_BASELINE",
                })
                continue
            desvio_duracao = None
            if c["duracao_dias"] is not None and atual.get("duracao_dias") is not None:
                desvio_duracao = round(atual["duracao_dias"] - c["duracao_dias"], 4)
            comparacao.append({
                "atividade_id": c["atividade_id"],
                "nome": atual.get("nome"),
                "data_fim_planejada_baseline": c["data_fim_planejada"],
                "data_fim_planejada_atual": atual.get("data_fim_planejada"),
                "duracao_baseline": c["duracao_dias"],
                "duracao_atual": atual.get("duracao_dias"),
                "desvio_duracao_dias": desvio_duracao,
                "percentual_concluido": atual.get("percentual_concluido"),
            })

    return {"baseline": bl, "comparacao": comparacao}
