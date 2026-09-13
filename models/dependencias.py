"""Dependências (precedência) entre atividades — as 4 relações do PERT/CPM.

TI (término-início): sucessora só começa quando a predecessora termina (a
mais comum, default). II (início-início), TT (término-término),
IT (início-término, rara). ``lag_dias`` desloca a relação (positivo =
espera extra; negativo = antecipação/sobreposição).
"""

from __future__ import annotations

from typing import Any

from .atividades import buscar_atividade
from .db import DEFAULT_PROJECT_ID, TIPOS_DEPENDENCIA_VALIDOS, _connect, _gerar_id, _to_dict, _to_list


def criar_dependencia(
    predecessora_id: str,
    sucessora_id: str,
    tipo: str = "TI",
    lag_dias: float = 0,
    project_id: str | None = None,
) -> dict[str, Any]:
    if predecessora_id == sucessora_id:
        raise ValueError("Uma atividade não pode depender dela mesma.")
    tipo = (tipo or "TI").upper()
    if tipo not in TIPOS_DEPENDENCIA_VALIDOS:
        raise ValueError(
            f"tipo '{tipo}' inválido. Válidos: {', '.join(sorted(TIPOS_DEPENDENCIA_VALIDOS))}"
        )
    pred = buscar_atividade(predecessora_id)
    suc = buscar_atividade(sucessora_id)
    if pred is None:
        raise ValueError(f"Atividade predecessora '{predecessora_id}' não encontrada.")
    if suc is None:
        raise ValueError(f"Atividade sucessora '{sucessora_id}' não encontrada.")

    pid = project_id or pred.get("project_id") or DEFAULT_PROJECT_ID

    # Detecção de ciclo: se sucessora já alcança a predecessora (BFS na rede
    # atual + a nova aresta), rejeita — cronograma com ciclo é indefinido.
    if _existe_caminho(sucessora_id, predecessora_id, pid):
        raise ValueError(
            f"Dependência rejeitada: criar '{predecessora_id}' -> '{sucessora_id}' "
            "fecharia um ciclo na rede (a sucessora já é predecessora, direta ou "
            "indiretamente, da atividade que você está tentando tornar predecessora)."
        )

    did = _gerar_id("dep")
    with _connect() as conn:
        existe = conn.execute(
            "SELECT 1 FROM dependencia WHERE predecessora_id=? AND sucessora_id=?",
            (predecessora_id, sucessora_id),
        ).fetchone()
        if existe:
            raise ValueError("Essa dependência já existe entre essas duas atividades.")
        conn.execute(
            """
            INSERT INTO dependencia (id, project_id, predecessora_id, sucessora_id, tipo, lag_dias)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (did, pid, predecessora_id, sucessora_id, tipo, lag_dias),
        )
        conn.commit()
    return buscar_dependencia(did)  # type: ignore[return-value]


def buscar_dependencia(dependencia_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        cursor = conn.execute("SELECT * FROM dependencia WHERE id = ?", (dependencia_id,))
        return _to_dict(cursor.fetchone())


def listar_dependencias(
    project_id: str | None = None,
    atividade_id: str | None = None,
) -> list[dict[str, Any]]:
    pid = project_id or DEFAULT_PROJECT_ID
    where = ["project_id = ?"]
    params: list[Any] = [pid]
    if atividade_id:
        where.append("(predecessora_id = ? OR sucessora_id = ?)")
        params.extend([atividade_id, atividade_id])
    sql = f"SELECT * FROM dependencia WHERE {' AND '.join(where)} ORDER BY created_at"
    with _connect() as conn:
        cursor = conn.execute(sql, tuple(params))
    return _to_list(cursor.fetchall())


def deletar_dependencia(dependencia_id: str) -> dict[str, Any]:
    if buscar_dependencia(dependencia_id) is None:
        raise ValueError(f"Dependência '{dependencia_id}' não encontrada.")
    with _connect() as conn:
        conn.execute("DELETE FROM dependencia WHERE id = ?", (dependencia_id,))
        conn.commit()
    return {"deletado": True, "id": dependencia_id}


def _existe_caminho(origem: str, destino: str, project_id: str) -> bool:
    """BFS: existe algum caminho origem -> ... -> destino na rede atual?"""
    with _connect() as conn:
        cursor = conn.execute(
            "SELECT predecessora_id, sucessora_id FROM dependencia WHERE project_id = ?",
            (project_id,),
        )
        arestas = _to_list(cursor.fetchall())
    adjacencia: dict[str, list[str]] = {}
    for a in arestas:
        adjacencia.setdefault(a["predecessora_id"], []).append(a["sucessora_id"])

    visitados = {origem}
    fila = [origem]
    while fila:
        atual = fila.pop()
        if atual == destino:
            return True
        for prox in adjacencia.get(atual, []):
            if prox not in visitados:
                visitados.add(prox)
                fila.append(prox)
    return False


def validar_dependencias(project_id: str | None = None) -> dict[str, Any]:
    """Audita a rede: dependências órfãs (atividade deletada) e ciclos.

    Ciclos não deveriam existir se toda dependência passou por
    ``criar_dependencia`` (que já bloqueia na criação), mas a checagem
    fica aqui como auditoria — por exemplo, contra dados importados
    diretamente no banco.
    """
    pid = project_id or DEFAULT_PROJECT_ID
    problemas: list[str] = []
    deps = listar_dependencias(pid)

    ids_atividade = set()
    with _connect() as conn:
        cursor = conn.execute("SELECT id FROM atividade WHERE project_id = ?", (pid,))
        ids_atividade = {r["id"] for r in cursor.fetchall()}

    adjacencia: dict[str, list[str]] = {}
    for d in deps:
        if d["predecessora_id"] not in ids_atividade:
            problemas.append(
                f"Dependência '{d['id']}': predecessora '{d['predecessora_id']}' não existe."
            )
        if d["sucessora_id"] not in ids_atividade:
            problemas.append(
                f"Dependência '{d['id']}': sucessora '{d['sucessora_id']}' não existe."
            )
        adjacencia.setdefault(d["predecessora_id"], []).append(d["sucessora_id"])

    # Detecção de ciclo via DFS com pilha de recursão (cores branco/cinza/preto).
    cor: dict[str, str] = {}

    def _dfs(no: str, caminho: list[str]) -> list[str] | None:
        cor[no] = "cinza"
        for viz in adjacencia.get(no, []):
            if cor.get(viz) == "cinza":
                return caminho + [no, viz]
            if cor.get(viz) != "preto":
                achado = _dfs(viz, caminho + [no])
                if achado:
                    return achado
        cor[no] = "preto"
        return None

    for no in list(adjacencia.keys()):
        if cor.get(no) is None:
            ciclo = _dfs(no, [])
            if ciclo:
                problemas.append(f"Ciclo detectado na rede: {' -> '.join(ciclo)}")
                break

    return {
        "resumo": {
            "total_dependencias": len(deps),
            "total_problemas": len(problemas),
            "rede_valida": len(problemas) == 0,
        },
        "problemas": problemas,
    }
