"""CRUD de atividades — a unidade de tempo do cronograma.

Cada atividade referencia um nó da EAP via ``eap_ref`` (string opaca: pode
ser o ``eap_id`` display ou, de preferência, o ``uid`` estável do
mcp-eap-server). Duração pode ser determinística (``duracao_dias``) ou PERT
(otimista/provável/pessimista — ``duracao_esperada_pert`` calcula o valor
esperado por (O + 4M + P) / 6, a fórmula clássica do método).
"""

from __future__ import annotations

from typing import Any

from .db import DEFAULT_PROJECT_ID, _agora_iso, _connect, _gerar_id, _to_dict, _to_list

CAMPOS_ATUALIZAVEIS = (
    "nome", "duracao_dias", "duracao_otimista", "duracao_provavel",
    "duracao_pessimista", "percentual_concluido",
    "data_inicio_planejada", "data_fim_planejada",
    "data_inicio_real", "data_fim_real",
)


def duracao_esperada_pert(
    otimista: float | None, provavel: float | None, pessimista: float | None
) -> float | None:
    """Duração esperada PERT: (O + 4M + P) / 6. None se faltar algum valor."""
    if otimista is None or provavel is None or pessimista is None:
        return None
    return round((otimista + 4 * provavel + pessimista) / 6, 4)


def desvio_padrao_pert(otimista: float | None, pessimista: float | None) -> float | None:
    """Desvio padrão PERT: (P - O) / 6."""
    if otimista is None or pessimista is None:
        return None
    return round((pessimista - otimista) / 6, 4)


def criar_atividade(dados: dict[str, Any]) -> dict[str, Any]:
    """Cria uma atividade. ``eap_ref`` e ``nome`` são obrigatórios.

    Se otimista/provável/pessimista forem passados e ``duracao_dias`` não,
    a duração é derivada automaticamente pela fórmula PERT.
    """
    if not (dados.get("eap_ref") or "").strip():
        raise ValueError("eap_ref é obrigatório (aponta pro nó da EAP).")
    if not (dados.get("nome") or "").strip():
        raise ValueError("nome é obrigatório.")

    duracao = dados.get("duracao_dias")
    if duracao is None:
        duracao = duracao_esperada_pert(
            dados.get("duracao_otimista"),
            dados.get("duracao_provavel"),
            dados.get("duracao_pessimista"),
        )
    if duracao is not None and duracao < 0:
        raise ValueError("duracao_dias não pode ser negativa.")

    aid = _gerar_id("atv")
    project_id = dados.get("project_id") or DEFAULT_PROJECT_ID
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO atividade (
                id, project_id, eap_ref, nome, duracao_dias,
                duracao_otimista, duracao_provavel, duracao_pessimista,
                percentual_concluido, data_inicio_planejada, data_fim_planejada,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                aid, project_id, dados["eap_ref"], dados["nome"], duracao,
                dados.get("duracao_otimista"), dados.get("duracao_provavel"),
                dados.get("duracao_pessimista"),
                dados.get("percentual_concluido", 0),
                dados.get("data_inicio_planejada"), dados.get("data_fim_planejada"),
                _agora_iso(), _agora_iso(),
            ),
        )
        conn.commit()
    return buscar_atividade(aid)  # type: ignore[return-value]


def buscar_atividade(atividade_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        cursor = conn.execute("SELECT * FROM atividade WHERE id = ?", (atividade_id,))
        return _to_dict(cursor.fetchone())


def listar_atividades(
    project_id: str | None = None,
    eap_ref: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[dict[str, Any]]:
    pid = project_id or DEFAULT_PROJECT_ID
    where = ["project_id = ?"]
    params: list[Any] = [pid]
    if eap_ref:
        where.append("eap_ref = ?")
        params.append(eap_ref)
    sql = f"SELECT * FROM atividade WHERE {' AND '.join(where)} ORDER BY created_at"
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params.extend([int(limit), int(offset)])
    with _connect() as conn:
        cursor = conn.execute(sql, tuple(params))
    return _to_list(cursor.fetchall())


def contar_atividades(project_id: str | None = None) -> int:
    pid = project_id or DEFAULT_PROJECT_ID
    with _connect() as conn:
        cursor = conn.execute(
            "SELECT COUNT(*) AS n FROM atividade WHERE project_id = ?", (pid,)
        )
        row = cursor.fetchone()
    return row["n"] if row else 0


def atualizar_atividade(atividade_id: str, dados: dict[str, Any]) -> dict[str, Any]:
    existente = buscar_atividade(atividade_id)
    if existente is None:
        raise ValueError(f"Atividade '{atividade_id}' não encontrada.")

    campos: list[str] = []
    valores: list[Any] = []
    for campo in CAMPOS_ATUALIZAVEIS:
        if campo in dados:
            if campo == "percentual_concluido":
                pc = dados[campo]
                if pc is not None and not (0 <= pc <= 100):
                    raise ValueError("percentual_concluido deve estar entre 0 e 100.")
            campos.append(f"{campo} = ?")
            valores.append(dados[campo])
    if not campos:
        return existente

    # duração PERT recalculada se os três parâmetros ficarem completos após o update
    otimista = dados.get("duracao_otimista", existente.get("duracao_otimista"))
    provavel = dados.get("duracao_provavel", existente.get("duracao_provavel"))
    pessimista = dados.get("duracao_pessimista", existente.get("duracao_pessimista"))
    if "duracao_dias" not in dados:
        derivada = duracao_esperada_pert(otimista, provavel, pessimista)
        if derivada is not None:
            campos.append("duracao_dias = ?")
            valores.append(derivada)

    campos.append("updated_at = ?")
    valores.append(_agora_iso())
    valores.append(atividade_id)
    with _connect() as conn:
        conn.execute(
            f"UPDATE atividade SET {', '.join(campos)} WHERE id = ?", tuple(valores)
        )
        conn.commit()
    return buscar_atividade(atividade_id)  # type: ignore[return-value]


def deletar_atividade(atividade_id: str) -> dict[str, Any]:
    if buscar_atividade(atividade_id) is None:
        raise ValueError(f"Atividade '{atividade_id}' não encontrada.")
    with _connect() as conn:
        tem_dep = conn.execute(
            "SELECT COUNT(*) AS n FROM dependencia WHERE predecessora_id = ? OR sucessora_id = ?",
            (atividade_id, atividade_id),
        ).fetchone()["n"]
        if tem_dep:
            raise ValueError(
                f"Atividade '{atividade_id}' tem {tem_dep} dependência(s) ligada(s). "
                "Remova as dependências antes de deletar."
            )
        conn.execute("DELETE FROM atividade WHERE id = ?", (atividade_id,))
        conn.commit()
    return {"deletado": True, "id": atividade_id}


def salvar_resultado_cpm(atividade_id: str, campos_cpm: dict[str, Any]) -> None:
    """Grava es/ef/ls/lf/folga/critica calculados pelo módulo cpm.py."""
    with _connect() as conn:
        conn.execute(
            """
            UPDATE atividade SET es=?, ef=?, ls=?, lf=?, folga_total=?, folga_livre=?,
                                  critica=?, updated_at=?
            WHERE id = ?
            """,
            (
                campos_cpm["es"], campos_cpm["ef"], campos_cpm["ls"], campos_cpm["lf"],
                campos_cpm["folga_total"], campos_cpm["folga_livre"],
                1 if campos_cpm["critica"] else 0,
                _agora_iso(), atividade_id,
            ),
        )
        conn.commit()
