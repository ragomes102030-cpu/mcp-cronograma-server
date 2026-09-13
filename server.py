"""mcp-cronograma-server: PERT/CPM seguindo o roteiro de Aldo Dórea Mattos
(Planejamento e Controle de Obras) — atividades, precedência, caminho
crítico, folgas, linha de base e curva S.

Cada atividade referencia um nó do mcp-eap-server via ``eap_ref`` (uid ou
eap_id, string opaca — não há validação cruzada ao vivo nesta v1; ver
docstring de ``models/db.py``).
"""

from __future__ import annotations

import os
import sys
from typing import Annotated, Any, Callable

from mcp.server.fastmcp import FastMCP
from pydantic import Field

import models
import schemas

mcp = FastMCP(
    name="cronograma-server",
    instructions=(
        "Servidor MCP de cronograma (PERT/CPM), seguindo o roteiro de "
        "Aldo Dorea Mattos: atividades, duracoes, precedencia, caminho "
        "critico, folgas, linha de base e curva S. Cada atividade referencia "
        "um no da EAP via eap_ref (uid ou eap_id do mcp-eap-server). Use "
        "criar_atividade para cadastrar, criar_dependencia para ligar "
        "atividades, calcular_caminho_critico para obter ES/EF/LS/LF e "
        "folgas, salvar_baseline/comparar_baseline para acompanhar desvio "
        "de prazo, e curva_s para progresso acumulado planejado x realizado."
    ),
)


def _log(evento: str, **campos: Any) -> None:
    import json as _json
    print(_json.dumps({"evento": evento, **campos}, ensure_ascii=False), file=sys.stderr, flush=True)


def _seguro(fn: Callable[[], Any], tool_name: str = "tool", **contexto: Any) -> dict[str, Any]:
    try:
        _log("tool_inicio", tool=tool_name, **contexto)
        resultado = fn()
        _log("tool_fim", tool=tool_name, **contexto)
        return resultado
    except Exception as exc:
        _log("tool_erro", tool=tool_name, erro=str(exc), **contexto)
        return schemas.ErroOutput(erro=str(exc)).model_dump()


def _idempotente(request_id: str | None, tool_name: str, fn: Callable[[], Any], **contexto: Any) -> dict[str, Any]:
    if request_id:
        cacheado = models.verificar_idempotencia(request_id)
        if cacheado is not None:
            return cacheado
    resultado = _seguro(fn, tool_name, **contexto)
    if request_id:
        models.salvar_idempotencia(request_id, tool_name, resultado)
    return resultado


# ── Atividades ──────────────────────────────────────────────────────────

@mcp.tool()
def criar_atividade(
    eap_ref: Annotated[str, Field(description="uid ou eap_id do nó correspondente no mcp-eap-server.")],
    nome: Annotated[str, Field(description="Nome da atividade.")],
    project_id: Annotated[str | None, Field(description="Projeto (obra). Omitir = 'default'.")] = None,
    duracao_dias: Annotated[float | None, Field(description="Duração determinística em dias. Omita se for usar PERT.", ge=0)] = None,
    duracao_otimista: Annotated[float | None, Field(description="Duração otimista (PERT), em dias.", ge=0)] = None,
    duracao_provavel: Annotated[float | None, Field(description="Duração mais provável (PERT), em dias.", ge=0)] = None,
    duracao_pessimista: Annotated[float | None, Field(description="Duração pessimista (PERT), em dias.", ge=0)] = None,
    data_inicio_planejada: Annotated[str | None, Field(description="Data ISO (YYYY-MM-DD), opcional.")] = None,
    data_fim_planejada: Annotated[str | None, Field(description="Data ISO (YYYY-MM-DD), opcional.")] = None,
    request_id: Annotated[str | None, Field(description="Idempotência: mesmo request_id devolve a mesma resposta.")] = None,
) -> dict[str, Any]:
    """Cria uma atividade de cronograma vinculada a um nó da EAP.

    Se otimista/provável/pessimista forem informados e duracao_dias não,
    a duração é calculada pela fórmula PERT: (O + 4M + P) / 6.
    """
    def _executar() -> dict[str, Any]:
        dados = {
            "eap_ref": eap_ref, "nome": nome, "project_id": project_id,
            "duracao_dias": duracao_dias, "duracao_otimista": duracao_otimista,
            "duracao_provavel": duracao_provavel, "duracao_pessimista": duracao_pessimista,
            "data_inicio_planejada": data_inicio_planejada, "data_fim_planejada": data_fim_planejada,
        }
        atividade = models.criar_atividade(dados)
        return schemas.AtividadeOutput(**atividade).model_dump()

    return _idempotente(request_id, "criar_atividade", _executar, eap_ref=eap_ref)


@mcp.tool()
def atualizar_atividade(
    atividade_id: Annotated[str, Field(description="ID da atividade (retornado por criar_atividade).")],
    nome: Annotated[str | None, Field(description="Novo nome.")] = None,
    duracao_dias: Annotated[float | None, Field(description="Nova duração determinística, em dias.", ge=0)] = None,
    duracao_otimista: Annotated[float | None, Field(ge=0)] = None,
    duracao_provavel: Annotated[float | None, Field(ge=0)] = None,
    duracao_pessimista: Annotated[float | None, Field(ge=0)] = None,
    percentual_concluido: Annotated[float | None, Field(description="Progresso (0-100).", ge=0, le=100)] = None,
    data_inicio_planejada: Annotated[str | None, Field(description="Data ISO.")] = None,
    data_fim_planejada: Annotated[str | None, Field(description="Data ISO.")] = None,
    data_inicio_real: Annotated[str | None, Field(description="Data ISO (realizado).")] = None,
    data_fim_real: Annotated[str | None, Field(description="Data ISO (realizado).")] = None,
) -> dict[str, Any]:
    """Atualiza campos de uma atividade existente (inclui progresso realizado)."""
    def _executar() -> dict[str, Any]:
        dados = {k: v for k, v in {
            "nome": nome, "duracao_dias": duracao_dias,
            "duracao_otimista": duracao_otimista, "duracao_provavel": duracao_provavel,
            "duracao_pessimista": duracao_pessimista,
            "percentual_concluido": percentual_concluido,
            "data_inicio_planejada": data_inicio_planejada, "data_fim_planejada": data_fim_planejada,
            "data_inicio_real": data_inicio_real, "data_fim_real": data_fim_real,
        }.items() if v is not None}
        atividade = models.atualizar_atividade(atividade_id, dados)
        return schemas.AtividadeOutput(**atividade).model_dump()

    return _seguro(_executar, "atualizar_atividade", atividade_id=atividade_id)


@mcp.tool()
def listar_atividades(
    project_id: Annotated[str | None, Field(description="Projeto (obra). Omitir = 'default'.")] = None,
    eap_ref: Annotated[str | None, Field(description="Filtrar por um nó específico da EAP.")] = None,
    limit: Annotated[int | None, Field(description="Máximo a retornar. Omitido = todos.", ge=1, le=500)] = None,
    offset: Annotated[int, Field(ge=0)] = 0,
) -> dict[str, Any]:
    """Lista atividades de um projeto de cronograma."""
    def _executar() -> dict[str, Any]:
        atividades = models.listar_atividades(project_id, eap_ref, limit, offset)
        return {
            "atividades": atividades,
            "total": models.contar_atividades(project_id),
            "retornados": len(atividades),
            "offset": offset,
        }

    return _seguro(_executar, "listar_atividades", project_id=project_id)


@mcp.tool()
def deletar_atividade(atividade_id: Annotated[str, Field(description="ID da atividade.")]) -> dict[str, Any]:
    """Deleta uma atividade (falha se houver dependências ligadas a ela)."""
    return _seguro(lambda: models.deletar_atividade(atividade_id), "deletar_atividade", atividade_id=atividade_id)


# ── Dependências ────────────────────────────────────────────────────────

@mcp.tool()
def criar_dependencia(
    predecessora_id: Annotated[str, Field(description="ID da atividade predecessora.")],
    sucessora_id: Annotated[str, Field(description="ID da atividade sucessora.")],
    tipo: Annotated[str, Field(description="TI (término-início, default), II, TT ou IT.")] = "TI",
    lag_dias: Annotated[float, Field(description="Deslocamento em dias (negativo = antecipação/sobreposição).")] = 0,
    request_id: Annotated[str | None, Field(description="Idempotência.")] = None,
) -> dict[str, Any]:
    """Cria uma dependência entre duas atividades. Rejeita se fechar um ciclo na rede."""
    def _executar() -> dict[str, Any]:
        dep = models.criar_dependencia(predecessora_id, sucessora_id, tipo, lag_dias)
        return schemas.DependenciaOutput(**dep).model_dump()

    return _idempotente(
        request_id, "criar_dependencia", _executar,
        predecessora_id=predecessora_id, sucessora_id=sucessora_id,
    )


@mcp.tool()
def listar_dependencias(
    project_id: Annotated[str | None, Field(description="Projeto (obra). Omitir = 'default'.")] = None,
    atividade_id: Annotated[str | None, Field(description="Filtrar dependências que envolvem esta atividade (como predecessora ou sucessora).")] = None,
) -> dict[str, Any]:
    """Lista dependências de um projeto (ou de uma atividade específica)."""
    def _executar() -> dict[str, Any]:
        deps = models.listar_dependencias(project_id, atividade_id)
        return {"dependencias": deps, "total": len(deps)}

    return _seguro(_executar, "listar_dependencias", project_id=project_id)


@mcp.tool()
def deletar_dependencia(dependencia_id: Annotated[str, Field(description="ID da dependência.")]) -> dict[str, Any]:
    """Remove uma dependência entre duas atividades."""
    return _seguro(lambda: models.deletar_dependencia(dependencia_id), "deletar_dependencia")


@mcp.tool()
def validar_dependencias(project_id: Annotated[str | None, Field(description="Projeto (obra). Omitir = 'default'.")] = None) -> dict[str, Any]:
    """Audita a rede de dependências: órfãs e ciclos."""
    return _seguro(lambda: models.validar_dependencias(project_id), "validar_dependencias", project_id=project_id)


# ── Caminho crítico / cronograma ────────────────────────────────────────

@mcp.tool()
def calcular_caminho_critico(
    project_id: Annotated[str | None, Field(description="Projeto (obra). Omitir = 'default'.")] = None,
) -> dict[str, Any]:
    """Calcula ES/EF/LS/LF e folgas de todas as atividades (CPM) e persiste
    o resultado. Retorna a duração total do projeto e o caminho crítico."""
    def _executar() -> dict[str, Any]:
        pid = project_id or models.DEFAULT_PROJECT_ID
        resultado = models.calcular_caminho_critico(pid)
        return schemas.CaminhoCriticoOutput(**resultado).model_dump()

    return _seguro(_executar, "calcular_caminho_critico", project_id=project_id)


# ── Baseline ────────────────────────────────────────────────────────────

@mcp.tool()
def salvar_baseline(
    nome: Annotated[str, Field(description="Nome da linha de base (ex.: 'Aprovada - Rev 0').")],
    project_id: Annotated[str | None, Field(description="Projeto (obra). Omitir = 'default'.")] = None,
) -> dict[str, Any]:
    """Congela o cronograma atual (datas planejadas + durações) como linha de base."""
    def _executar() -> dict[str, Any]:
        pid = project_id or models.DEFAULT_PROJECT_ID
        return models.salvar_baseline(pid, nome)

    return _seguro(_executar, "salvar_baseline", project_id=project_id)


@mcp.tool()
def listar_baselines(project_id: Annotated[str | None, Field(description="Projeto (obra). Omitir = 'default'.")] = None) -> dict[str, Any]:
    """Lista as linhas de base salvas de um projeto."""
    def _executar() -> dict[str, Any]:
        baselines = models.listar_baselines(project_id)
        return {"baselines": baselines, "total": len(baselines)}

    return _seguro(_executar, "listar_baselines", project_id=project_id)


@mcp.tool()
def comparar_baseline(baseline_id: Annotated[str, Field(description="ID da linha de base.")]) -> dict[str, Any]:
    """Compara uma linha de base contra o estado atual (desvio de prazo)."""
    return _seguro(lambda: models.comparar_baseline(baseline_id), "comparar_baseline", baseline_id=baseline_id)


# ── Curva S ─────────────────────────────────────────────────────────────

@mcp.tool()
def curva_s(project_id: Annotated[str | None, Field(description="Projeto (obra). Omitir = 'default'. Requer calcular_caminho_critico rodado antes.")] = None) -> dict[str, Any]:
    """Gera os pontos da curva S (progresso acumulado planejado x realizado)."""
    def _executar() -> dict[str, Any]:
        pid = project_id or models.DEFAULT_PROJECT_ID
        return models.curva_s(pid)

    return _seguro(_executar, "curva_s", project_id=project_id)


# ── Boot ──────────────────────────────────────────────────────────────

models.init_db()

app = mcp.streamable_http_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)
