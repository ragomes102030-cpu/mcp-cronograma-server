"""MCP publico: calculos em memoria, sem ler ou alterar bancos de obras."""
from __future__ import annotations
import math
from collections import deque
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp_http_security import allowed_mcp_hosts
from mcp_public_origins import allowed_public_origins

public_mcp = MCPServer(
    name="arquimedes-cronograma-publico",
    instructions=("Calculos anonimos em memoria e sem persistencia de obras. "
                  "Nenhuma atividade, dependencia, baseline ou projeto e alterado."),

)

@public_mcp.tool()
def calcular_duracao_com_evidencia(
    quantidade: float, produtividade: float, unidade: str,
    unidade_produtividade: str, fonte: str | None = None
) -> dict:
    """Calcula ceil(quantidade/produtividade); nao presume produtividade nem converte unidades."""
    if not all(math.isfinite(x) and 0 < x <= 1e9 for x in (quantidade, produtividade)):
        raise ValueError("Quantidade e produtividade devem ser positivas, finitas e <= 1e9.")
    unidade_base = unidade.strip().lower()
    unidade_taxa = unidade_produtividade.strip().lower()
    # Produtividade por dia: aceitar tanto "m²" (legado) quanto "m²/dia".
    # Nao converter unidades fisicas nem aceitar denominadores desconhecidos.
    if not unidade_base or not unidade_taxa or unidade_taxa not in (unidade_base, unidade_base + "/dia"):
        raise ValueError("Unidades nao compativeis: use a unidade da quantidade ou unidade/dia.")
    return {"duracaoDias": math.ceil(quantidade/produtividade), "quantidade": quantidade,
            "produtividade": produtividade, "unidade": unidade,
            "evidenceLevel": "source_supported" if fonte and fonte.strip() else "engineer_informed",
            "fonte": fonte, "persistido": False}

@public_mcp.tool()
def calcular_cpm_com_evidencia(atividades: list[dict], dependencias: list[dict]) -> dict:
    """CPM em memoria. TI/FS, II/SS, TT/FF, IT/SF; duracoes em dias, lag positivo ou negativo."""
    if not isinstance(atividades,list) or not isinstance(dependencias,list):
        raise ValueError("Forneca duas listas.")
    if not 1 <= len(atividades) <= 2000 or not 0 <= len(dependencias) <= 10000:
        raise ValueError("Limite: 1-2000 atividades, 0-10000 dependencias.")
    dur: dict[str, float] = {}
    for a in atividades:
        if not isinstance(a,dict) or not str(a.get("id") or "").strip():
            raise ValueError("Toda atividade precisa de id.")
        ident = str(a["id"]).strip()
        if len(ident)>100 or ident in dur:
            raise ValueError("ID duplicado ou excessivamente longo.")
        try: d=float(a["duracao_dias"])
        except (KeyError,TypeError,ValueError): raise ValueError(f"{ident}: duracao_dias ausente/invalida")
        if not math.isfinite(d) or not 0 < d <= 1e6:
            raise ValueError(f"{ident}: duracao_dias deve ser positiva e finita")
        dur[ident]=d
    edges=[]
    for dep in dependencias:
        if not isinstance(dep,dict): raise ValueError("Dependencia invalida")
        p=str(dep.get("predecessora_id") or "").strip()
        s=str(dep.get("sucessora_id") or "").strip()
        t=str(dep.get("tipo","TI")).upper()
        t={"FS":"TI","SS":"II","FF":"TT","SF":"IT"}.get(t,t)
        try: lag=float(dep.get("lag_dias",0) or 0)
        except (TypeError,ValueError): raise ValueError("lag_dias invalido")
        if p not in dur or s not in dur or p==s:
            return {**diagnosticar_rede_cpm(atividades, dependencias),
                    "valid": False,
                    "erro": "Dependencia com ID inexistente ou auto-referencia"}
        if t not in ("TI","II","TT","IT") or not math.isfinite(lag) or abs(lag)>1e6:
            raise ValueError("Tipo/lag de dependencia invalido")
        # Constraint: ES[s] >= ES[p] + weight
        w={"TI":dur[p]+lag,"II":lag,"TT":dur[p]+lag-dur[s],"IT":lag-dur[s]}[t]
        edges.append((p,s,w))
    incoming={x:[] for x in dur}
    outgoing={x:[] for x in dur}
    degree={x:0 for x in dur}
    for p,s,w in edges:
        incoming[s].append((p,w))
        outgoing[p].append((s,w))
        degree[s]+=1
    fila=deque(x for x in dur if degree[x]==0)
    ordem=[]
    while fila:
        x=fila.popleft();ordem.append(x)
        for s,_ in outgoing[x]:
            degree[s]-=1
            if degree[s]==0:fila.append(s)
    if len(ordem)!=len(dur):
        return {**diagnosticar_rede_cpm(atividades, dependencias),
                "valid": False, "erro": "Rede com ciclo: CPM recusado"}
    if len(dur)>1 and not edges:
        return {**diagnosticar_rede_cpm(atividades, dependencias),
                "valid": False,
                "erro": "Rede vazia de dependencias: informe a sequencia de atividades"}
    es={x:0.0 for x in dur}
    for x in ordem:
        for s,w in outgoing[x]:
            es[s]=max(es[s],es[x]+w)
    ef={x:es[x]+dur[x] for x in dur}
    prazo=max(ef.values())
    # Latest starts obey all precedence constraints and project deadline.
    ls={x:prazo-dur[x] for x in dur}
    for x in reversed(ordem):
        for s,w in outgoing[x]:
            ls[x]=min(ls[x],ls[s]-w)
    resultados=[]
    for x in ordem:
        folga=ls[x]-es[x]
        # Folga livre: maior deslocamento que nao altera datas cedo dos
        # sucessores nem o prazo de conclusao da obra. As restricoes
        # generalizadas TI/II/TT/IT sao ponderadas por w.
        margens = [prazo - ef[x]]
        margens.extend(es[s] - es[x] - w for s,w in outgoing[x])
        folga_livre = max(0.0, min(margens))
        resultados.append({"id":x,"duracao_dias":dur[x],"ES":round(es[x],6),
            "EF":round(ef[x],6),"LS":round(ls[x],6),"LF":round(ls[x]+dur[x],6),
            "folga_total":round(folga,6),"folga_livre":round(folga_livre,6),
            "critica":abs(folga)<1e-6})
    # Preserve the legacy list of critical activities, but also return
    # actual ordered paths with tight precedence links. The project may
    # have multiple paths; cap enumeration to avoid exponential output.
    critical = {x for x in dur if abs(ls[x] - es[x]) < 1e-6}
    tight_adj = {x: [] for x in critical}
    tight_in = {x: 0 for x in critical}
    for pred, succ, weight in edges:
        if (pred in critical and succ in critical and
                abs(es[succ] - es[pred] - weight) < 1e-6 and
                succ not in tight_adj[pred]):
            tight_adj[pred].append(succ)
            tight_in[succ] += 1
    roots = [x for x in ordem if x in critical and
             not tight_in[x] and abs(es[x]) < 1e-6]
    caminhos_criticos = []
    limite_caminhos = 128
    caminhos_truncados = False

    # DFS iterativa: redes extensas nao estouram o limite de recursao Python.
    # Preserva ordem deterministica, no maximo 128 caminhos completos.
    for raiz in roots:
        pilha: list[tuple[str, list[str]]] = [(raiz, [raiz])]
        while pilha:
            atual, caminho = pilha.pop()
            proximos = tight_adj[atual]
            if not proximos:
                if abs(ef[atual] - prazo) < 1e-6:
                    if len(caminhos_criticos) >= limite_caminhos:
                        caminhos_truncados = True
                        break
                    caminhos_criticos.append(caminho)
                continue
            for proximo in reversed(proximos):
                pilha.append((proximo, caminho + [proximo]))
        if caminhos_truncados:
            break
    vinculadas = {ident for p,s,_ in edges for ident in (p,s)}
    sem_vinculo = [ident for ident in dur if ident not in vinculadas] if len(dur) > 1 else []
    return {"valid":True,"duracao_projeto_dias":round(prazo,6),
            "atividades_sem_vinculo":sem_vinculo,
            "atividades":resultados,
            "caminho_critico":[r["id"] for r in resultados if r["critica"]],
            "caminhos_criticos":caminhos_criticos,
            "caminhos_criticos_truncados":caminhos_truncados,
            "origem":"dados_da_chamada","persistido":False,
            "premissa":"tempos relativos; calendario de trabalho nao aplicado"}

@public_mcp.tool()
def diagnosticar_rede_cpm(atividades: list[dict], dependencias: list[dict]) -> dict:
    """Diagnostica ciclos, referencias invalidas e atividades isoladas sem persistencia."""
    erros: list[dict] = []
    if not isinstance(atividades, list) or not isinstance(dependencias, list):
        return {"valid": False, "erros": [{"codigo": "ENTRADA_INVALIDA"}], "persistido": False}
    if not 1 <= len(atividades) <= 2000 or len(dependencias) > 10000:
        return {"valid": False, "erros": [{"codigo": "LIMITE_EXCEDIDO"}], "persistido": False}
    ids: set[str] = set()
    for a in atividades:
        if not isinstance(a, dict) or not str(a.get("id") or "").strip():
            erros.append({"codigo": "ATIVIDADE_SEM_ID"})
            continue
        ident = str(a["id"]).strip()
        if ident in ids:
            erros.append({"codigo": "ID_DUPLICADO", "atividade": ident})
        ids.add(ident)
    adj: dict[str, list[str]] = {ident: [] for ident in ids}
    grau = {ident: 0 for ident in ids}
    vinculadas: set[str] = set()
    for dep in dependencias:
        if not isinstance(dep, dict):
            erros.append({"codigo": "DEPENDENCIA_INVALIDA"})
            continue
        p = str(dep.get("predecessora_id") or "").strip()
        s = str(dep.get("sucessora_id") or "").strip()
        if p not in ids or s not in ids:
            erros.append({"codigo": "REFERENCIA_INEXISTENTE", "predecessora_id": p, "sucessora_id": s})
        elif p == s:
            erros.append({"codigo": "AUTO_REFERENCIA", "atividade": p})
        else:
            adj[p].append(s)
            grau[s] += 1
            vinculadas.update((p, s))
    fila = [x for x in ids if grau[x] == 0]
    visitados = 0
    while fila:
        x = fila.pop()
        visitados += 1
        for s in adj[x]:
            grau[s] -= 1
            if grau[s] == 0:
                fila.append(s)
    if visitados < len(ids):
        erros.append({"codigo": "CICLO", "atividades_envolvidas_ou_bloqueadas": sorted(x for x in ids if grau[x] > 0)})
    if len(ids) > 1 and not dependencias:
        erros.append({"codigo": "REDE_SEM_DEPENDENCIAS"})
    return {"valid": not erros, "erros": erros,
            "atividades_sem_vinculo": sorted(ids - vinculadas) if len(ids) > 1 else [],
            "persistido": False, "origem": "dados_da_chamada"}


@public_mcp.tool()
def calcular_cpm_com_calendario(
    atividades: list[dict], dependencias: list[dict], data_inicio: str,
    calendario: dict,
) -> dict:
    """Calcula CPM deterministico com calendario explicito e fim exclusivo.

    Preserva a ferramenta original. Modo uteis exige duracao e lag em
    dias inteiros, dias_semana (0=seg) e feriados ISO; nao consulta DB.
    """
    from models.cpm_calendario import aplicar_calendario_cpm

    # Fail-closed: do not infer fractional working days by rounding.
    if not isinstance(calendario, dict):
        raise ValueError("Calendario precisa ser explicito.")
    if calendario.get("modo") == "uteis":
        from models.cpm_calendario import _integer
        if not isinstance(atividades, list) or not isinstance(dependencias, list):
            raise ValueError("Atividades e dependencias precisam ser listas.")
        for a in atividades:
            if not isinstance(a, dict):
                raise ValueError("Atividade invalida.")
            _integer(a.get("duracao_dias"), "duracao_dias", positive=True)
        for dep in dependencias:
            if not isinstance(dep, dict):
                raise ValueError("Dependencia invalida.")
            _integer(dep.get("lag_dias", 0) or 0, "lag_dias")
    resultado = calcular_cpm_com_evidencia(atividades, dependencias)
    return aplicar_calendario_cpm(resultado, atividades, dependencias, data_inicio, calendario)


@public_mcp.tool()
def comparar_baseline_sem_persistencia(baseline: list[dict], atual: list[dict]) -> dict:
    """Compara snapshots fornecidos pelo cliente, sem consultar nem alterar obras."""
    from models.baseline_comparison import comparar_baseline_em_memoria
    return comparar_baseline_em_memoria(baseline, atual)


def create_public_app():
    """Create an isolated stateless public ASGI app for a legacy HTTP request."""
    request_server = MCPServer(
        name="arquimedes-cronograma-publico",
        instructions=("Calculos anonimos em memoria e sem persistencia de obras. "
                      "Nenhuma atividade, dependencia, baseline ou projeto e alterado."),
    )
    request_server.add_tool(calcular_duracao_com_evidencia)
    request_server.add_tool(calcular_cpm_com_evidencia)
    request_server.add_tool(diagnosticar_rede_cpm)
    request_server.add_tool(calcular_cpm_com_calendario)
    request_server.add_tool(comparar_baseline_sem_persistencia)
    return request_server.streamable_http_app(
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_origins=allowed_public_origins(),
            allowed_hosts=allowed_mcp_hosts(
                "arquimedes-mcp-cronograma.vercel.app",
                "mcp-cronograma-server.onrender.com",
            ),
        ),
    )


public_app = create_public_app()
