"""MCP publico: calculos em memoria, sem ler ou alterar bancos de obras."""
from __future__ import annotations
import math
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

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
    if not unidade.strip() or unidade.strip().lower() != unidade_produtividade.strip().lower():
        raise ValueError("Unidades nao compativeis.")
    return {"duracaoDias": math.ceil(quantidade/produtividade), "quantidade": quantidade,
            "produtividade": produtividade, "unidade": unidade,
            "evidenceLevel": "source_supported" if fonte and fonte.strip() else "engineer_informed",
            "fonte": fonte, "persistido": False}

@public_mcp.tool()
def calcular_cpm_com_evidencia(atividades: list[dict], dependencias: list[dict]) -> dict:
    """CPM em memoria. TI/FS, II/SS, TT/FF, IT/SF; duracoes em dias, lag positivo ou negativo."""
    if not isinstance(atividades,list) or not isinstance(dependencias,list):
        raise ValueError("Forneca duas listas.")
    if not 1 <= len(atividades) <= 150 or not 0 <= len(dependencias) <= 400:
        raise ValueError("Limite: 1-150 atividades, 0-400 dependencias.")
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
        try: lag=float(dep.get("lag_dias",0) or 0)
        except (TypeError,ValueError): raise ValueError("lag_dias invalido")
        if p not in dur or s not in dur or p==s: raise ValueError("Dependencia com ID inexistente ou auto-referencia")
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
    fila=[x for x in dur if degree[x]==0]
    ordem=[]
    while fila:
        x=fila.pop(0);ordem.append(x)
        for s,_ in outgoing[x]:
            degree[s]-=1
            if degree[s]==0:fila.append(s)
    if len(ordem)!=len(dur): raise ValueError("Rede com ciclo: CPM recusado")
    if len(dur)>1 and not edges:
        raise ValueError("Rede vazia de dependencias: informe a sequencia de atividades")
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
        resultados.append({"id":x,"duracao_dias":dur[x],"ES":round(es[x],6),
            "EF":round(ef[x],6),"LS":round(ls[x],6),"LF":round(ls[x]+dur[x],6),
            "folga_total":round(folga,6),"critica":abs(folga)<1e-6})
    return {"valid":True,"duracao_projeto_dias":round(prazo,6),
            "atividades":resultados,
            "caminho_critico":[r["id"] for r in resultados if r["critica"]],
            "origem":"dados_da_chamada","persistido":False,
            "premissa":"tempos relativos; calendario de trabalho nao aplicado"}

public_app = public_mcp.streamable_http_app(
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["arquimedes-mcp-cronograma.vercel.app", "*.vercel.app", "localhost:*", "127.0.0.1:*"],
    ),
)
