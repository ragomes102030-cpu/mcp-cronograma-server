#!/usr/bin/env python3
"""QA-only completion of nine EAP dictionaries and non-mutating LOB balance study.

Uses EXACT known fictitious project from authenticated 4-floor run.
All URLs/tokens come from guarded QA GitHub Actions secrets.
NO edits to existing Cronograma activities, CPM, approved baseline, or LOB.
"""
from __future__ import annotations

from datetime import date
from hashlib import sha256
import json
import os
from pathlib import Path
import re

from scripts.qa_three_private_mcps import Mcp, config_from_env
from scripts.qa_private_four_floor_complete import PACKAGES, FLOORS, START

QA_PROJECT = "qa-obra4p-741e8662e406"
QA_CONFIRM = "YES_QA_ONLY"
# "Responsavel" values below are QA role placeholders, NOT assignment of real staff.
# Every acceptance requirement is a written QA criterion: no regulatory approval.
DICTIONARY = {
    "mobilizacao": {
        "inclusoes": "Instalação, sinalização preliminar e organização do canteiro fictício.",
        "exclusoes": "Operação permanente do canteiro e licenças não apresentadas.",
        "medicao": "Contar unidades de implantação verificadas por checklist fotográfico e registro QA; sem validar licenças.",
        "aceite": "Checklist de instalações provisórias, acessos e segurança assinado pelo revisor QA.",
        "responsavel": "Papel QA - Encarregado de mobilização", "disciplina": "Produção"},
    "fundacao": {
        "inclusoes": "Concretagem de elementos de fundação definidos no escopo de teste.",
        "exclusoes": "Serviços geotécnicos ou reforços não previstos no quantitativo fictício.",
        "medicao": "Volume geométrico executado em m³ conforme dimensões registradas e conferidas; sem contar perdas.",
        "aceite": "Conferência de locação, formas, aço e registros de concreto pelo responsável técnico fictício.",
        "responsavel": "Papel QA - Engenheiro de estruturas", "disciplina": "Estruturas"},
    "estrutura": {
        "inclusoes": "Execução do conjunto estrutural em quatro pavimentos, com quantitativos fictícios por área.",
        "exclusoes": "Fundação, alvenaria e equipamentos que não integram a medição do pacote.",
        "medicao": "Área de estrutura em m² por pavimento concluído e inspecionado; somar 4 × 80 m² sem dupla contagem.",
        "aceite": "Geometria, nível, cobrimento e documentação dos materiais conferidos em inspeção QA.",
        "responsavel": "Papel QA - Supervisor de estrutura", "disciplina": "Estruturas"},
    "alvenaria": {
        "inclusoes": "Elevação de alvenarias de vedação nos quatro pavimentos.",
        "exclusoes": "Revestimentos, impermeabilização e divisórias fora do pacote.",
        "medicao": "Área de alvenaria executada em m² por pavimento; critérios de desconto de vãos devem constar da medição QA.",
        "aceite": "Prumo, alinhamento, juntas e interfaces com instalações inspecionados e registrados.",
        "responsavel": "Papel QA - Encarregado de alvenaria", "disciplina": "Civil"},
    "hidro": {
        "inclusoes": "Pontos e trechos hidrossanitários contemplados no modelo fictício.",
        "exclusoes": "Equipamentos e dispositivos não relacionados aos 80 pontos previstos.",
        "medicao": "Contar pontos hidrossanitários executados, identificados por pavimento e registrados; total-alvo 80 pt.",
        "aceite": "Testes funcionais/estanqueidade registrados, interferências tratadas e documentação de inspeção QA.",
        "responsavel": "Papel QA - Encarregado hidrossanitário", "disciplina": "Hidrossanitária"},
    "revestimento": {
        "inclusoes": "Revestimentos de quatro pavimentos previstos no modelo QA.",
        "exclusoes": "Pintura final, esquadrias e retrabalhos não aprovados.",
        "medicao": "Área acabada aceita em m² por pavimento; total 4 × 100 m², sem contabilizar áreas rejeitadas.",
        "aceite": "Regularidade superficial, aderência e acabamento conferidos em checklist QA.",
        "responsavel": "Papel QA - Encarregado de acabamento", "disciplina": "Acabamentos"},
    "cobertura": {
        "inclusoes": "Cobertura, caimentos e impermeabilização da área prevista.",
        "exclusoes": "Manutenção posterior e áreas externas não contempladas.",
        "medicao": "Medir em m² as áreas de cobertura/impermeabilização concluídas e aceitas; total de referência 120 m².",
        "aceite": "Detalhes, caimentos, arremates e teste de estanqueidade documentados na simulação QA.",
        "responsavel": "Papel QA - Supervisor de cobertura", "disciplina": "Impermeabilização"},
    "comissionamento": {
        "inclusoes": "Quatro etapas fictícias de comissionamento e verificação técnica.",
        "exclusoes": "Operação permanente e reparos fora do escopo original.",
        "medicao": "Contar etapas concluídas, cada uma vinculada a relatório de teste e não conformidades resolvidas.",
        "aceite": "Resultados de testes, pendências tratadas e evidências formalizadas em relatório QA.",
        "responsavel": "Papel QA - Coordenador de comissionamento", "disciplina": "Qualidade"},
    "entrega": {
        "inclusoes": "Consolidação e entrega técnica da obra fictícia.",
        "exclusoes": "Garantias futuras e assistência pós-entrega.",
        "medicao": "Uma entrega técnica aceita, condicionada à conferência do pacote documental de QA.",
        "aceite": "Documentação, desenhos conforme executado, termos de teste e lista de pendências revisados.",
        "responsavel": "Papel QA - Gestor de entrega técnica", "disciplina": "Gestão"},
}
SERVICE_KEYS = ("estrutura", "alvenaria", "hidro", "revestimento")
BASE_TEAMS = (1,1,1,1)
VARIANTS = (
    ("baseline_aprovada", (1,1,1,1)),
    ("alvenaria_2_equipes", (1,2,1,1)),
    ("estrutura_alvenaria_2_equipes", (2,2,1,1)),
    ("estrutura_2_equipes", (2,1,1,1)),
)


def build_dictionary(key: str) -> dict:
    if key not in DICTIONARY:
        raise ValueError(f"Pacote não cadastrado no dicionário QA: {key}")
    d=DICTIONARY[key]
    return {
        "descricao": (
            "INCLUSÕES: "+d["inclusoes"]+"\n"
            "EXCLUSÕES: "+d["exclusoes"]+"\n"
            "CRITÉRIO DE ACEITAÇÃO (QA): "+d["aceite"]+"\n"
            "OBSERVAÇÃO: premissas fictícias; não é laudo de conformidade normativa."
        ),
        "criterio_medicao": d["medicao"],
        "responsavel": d["responsavel"],
        "disciplina": d["disciplina"],
    }


def all_leaves(nodes: list[dict]) -> list[dict]:
    leaves=[]
    for n in nodes:
        kids=n.get("filhos") or []
        if kids:
            leaves.extend(all_leaves(kids))
        else:
            leaves.append(n)
    return leaves


def package_signature(n: dict) -> tuple:
    return (n.get("tipo_frente"),n.get("unidade"),float(n.get("quantidade") or 0))


def validate_scope_and_dictionary():
    assert len(DICTIONARY)==len(PACKAGES)==9
    assert set(DICTIONARY)=={p[0] for p in PACKAGES}
    signatures=[(p[2],p[3],float(p[4])) for p in PACKAGES]
    assert len(set(signatures))==9, "Ambiguous EAP packet signatures"
    assert sum(p[6] for p in PACKAGES)==100
    for key in DICTIONARY:
        d=build_dictionary(key)
        assert all(d.values()) and all(len(v.strip())>20 for v in d.values())
        assert all(tag in d["descricao"] for tag in ("INCLUSÕES:","EXCLUSÕES:","CRITÉRIO DE ACEITAÇÃO (QA):"))
        assert d["responsavel"].startswith("Papel QA - ")


def digest(v) -> str:
    return sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()


def run(cfg: dict, output_dir: Path):
    validate_scope_and_dictionary()
    assert QA_PROJECT=="qa-obra4p-741e8662e406"
    clients={n:Mcp(**cfg[n]) for n in ("eap","cronograma","lob")}
    needed={
        "eap":{"get_eap_tree","definir_criterio","pacotes_sem_dono","validar_estrutura"},
        "cronograma":{"listar_atividades","listar_baselines"},
        "lob":{"balancear_ritmos_lob","calcular_linha_balanco"},
    }
    for name,c in clients.items():
        tools=c.connect()
        if not needed[name].issubset(tools):
            raise AssertionError(f"{name}: tool catalog incomplete {sorted(needed[name]-tools)}")

    output_dir.mkdir(parents=True,exist_ok=True)
    calls=[]
    def call(server,tool,args):
        out=clients[server].call(tool,args)
        calls.append({"motor":server,"ferramenta":tool,"sha256":digest(out)})
        return out
    status={"projeto":QA_PROJECT,"status":"started","ambiente":"QA isolado",
            "cronograma_inalterado":False}
    try:
        old_acts=call("cronograma","listar_atividades",{"project_id":QA_PROJECT})
        old_bls=call("cronograma","listar_baselines",{"project_id":QA_PROJECT})
        assert old_acts["total"]==21 and old_bls["total"]==2
        approved_hashes={"activities":digest(old_acts),"baselines":digest(old_bls)}
        tree=call("eap","get_eap_tree",{"project_id":QA_PROJECT})
        assert len(tree.get("raizes",[]))==1
        leaves=all_leaves(tree["raizes"])
        assert len(leaves)==9
        mapped={}
        expected={(p[2],p[3],float(p[4])):p[0] for p in PACKAGES}
        for leaf in leaves:
            sign=package_signature(leaf)
            if sign not in expected:raise AssertionError(f"Unexpected EAP QA leaf signature {sign}")
            key=expected[sign]
            if key in mapped:raise AssertionError(f"Duplicate QA EAP package {key}")
            mapped[key]=leaf
        if set(mapped)!=set(DICTIONARY):raise AssertionError("Incomplete QA EAP map")

        # Fail closed if someone has already configured a different dictionary.
        # Read all nine leaves FIRST before any mutation.
        edits=[]
        for key in DICTIONARY:
            leaf=mapped[key]
            desired=build_dictionary(key)
            existing={k:leaf.get(k) for k in desired}
            if any(existing[k] not in (None,"",desired[k]) for k in desired):
                raise AssertionError(f"QA package {key} has pre-existing nonmatching dictionary; manual review required")
            if existing!=desired:
                edits.append((key,leaf,desired))

        for key,leaf,data in edits:
            result=call("eap","definir_criterio",{
                "project_id":QA_PROJECT,"uid":leaf["uid"],**data})
            if result.get("eap_id")!=leaf["eap_id"]:
                raise AssertionError(f"Mismatch read-back response for {key}")
            if any(result.get(field)!=val for field,val in data.items()):
                raise AssertionError(f"Dictionary write not acknowledged: {key}")
        tree_new=call("eap","get_eap_tree",{"project_id":QA_PROJECT})
        leaves_new=all_leaves(tree_new["raizes"])
        assert len(leaves_new)==9
        dict_rows=[]
        for leaf in leaves_new:
            key=expected[package_signature(leaf)]
            fields=build_dictionary(key)
            if any(leaf.get(f)!=v for f,v in fields.items()):
                raise AssertionError(f"Persistent dictionary read-back mismatch {key}")
            dict_rows.append({
                "codigo_eap":leaf["eap_id"],"pacote":key,
                "nome":leaf.get("nome"),"unidade":leaf["unidade"],
                "quantidade":leaf["quantidade"],"peso_percentual":next(p[6] for p in PACKAGES if p[0]==key),
                **fields})
        with_owners=call("eap","pacotes_sem_dono",{"project_id":QA_PROJECT})
        assert with_owners.get("total")==0, "QA project still has unowned leaf"
        validation=call("eap","validar_estrutura",{"project_id":QA_PROJECT})
        assert not validation.get("erros") and not any("SEM_DONO" in str(w) for w in validation.get("avisos",[]))

        base_specs=[{"nome":next(p[1] for p in PACKAGES if p[0]==k),
                     "tempo_unitario":int(next(p[4]/4/p[5] for p in PACKAGES if p[0]==k)),
                     "numero_equipes":1,"pulmao_dias":0} for k in SERVICE_KEYS]
        balance=call("lob","balancear_ritmos_lob",{"atividades":base_specs})
        suggestions=balance["sugestoes"]
        hydro=next(x for x in suggestions if x["nome"]==base_specs[2]["nome"])
        assert hydro.get("risco_interferencia") and hydro.get("equipes_predecessora_para_acelerar")==2

        scenarios=[]
        for name,counts in VARIANTS:
            specs=[{**a,"numero_equipes":team} for a,team in zip(base_specs,counts)]
            sim=call("lob","calcular_linha_balanco",{
                "atividades":specs,"unidades":list(FLOORS),
                "data_inicio":(START.replace(day=18)).isoformat()})
            wait={x["nome"]:x["espera_total_dias"] for x in sim["atividades"]}
            risk={x["nome"]:bool(x["risco_interferencia"]) for x in sim["atividades"]}
            scenarios.append({
                "cenario":name,"equipes":list(counts),
                "prazo_lob_dias":sim["duracao_total_dias"],
                "espera_dias_por_servico":wait,
                "riscos_interferencia":risk,
                "alterou_plano":False,
                "restricoes":"Produtividades e recursos supostos; nao substitui orcamento, validacao de campo ou CPM reprogramado",
            })
        assert [x["prazo_lob_dias"] for x in scenarios]==[30,28,26,28]
        hydro_name=base_specs[2]["nome"]
        assert [x["espera_dias_por_servico"][hydro_name] for x in scenarios]==[6,6,0,6]

        new_acts=call("cronograma","listar_atividades",{"project_id":QA_PROJECT})
        new_bls=call("cronograma","listar_baselines",{"project_id":QA_PROJECT})
        assert digest(new_acts)==approved_hashes["activities"]
        assert digest(new_bls)==approved_hashes["baselines"]
        assert new_bls["total"]==2 and sum(bool(x.get("ativa")) for x in new_bls["baselines"])==1
        status.update({
            "status":"passed","pacotes_dicionario_completos":len(dict_rows),
            "itens_eap_atualizados":len(edits),"pacotes_sem_dono":0,
            "avisos_eap":validation.get("avisos",[]),
            "regra_100_externa_percentual":100,
            "dicionario":sorted(dict_rows,key=lambda x:x["codigo_eap"]),
            "balanceamento_mcp":balance,"cenarios":scenarios,
            "baseline_ativa_preservada":True,"cronograma_inalterado":True,
            "baseline_hash_antes_depois":approved_hashes["baselines"],
            "atividades_hash_antes_depois":approved_hashes["activities"],
            "chamadas":calls,"criterio_aceitacao_campo_proprio":False,
            "ressalvas":[
                "Responsáveis são PAPÉIS fictícios de QA; não há nomeação real de profissionais.",
                "Aceitação registrada na descricao; EAP MCP ainda não tem coluna criterio_aceite.",
                "Regra dos 100% é externa: soma de pesos, não mecanismo nativo EAP.",
                "Cenários de equipes são simulações sem aprovação ou alteração do cronograma.",
                "Critérios técnicos não equivalem a aprovação legal ou normativa."
            ]
        })
        (output_dir/"qa_dicionario_e_balanceamento.json").write_text(
            json.dumps(status,ensure_ascii=False,indent=2),encoding="utf8")
        return status
    except Exception as exc:
        status.update({"status":"failed","erro":type(exc).__name__+": "+str(exc),
                       "ultimas_chamadas":calls[-5:]})
        (output_dir/"qa_falha_dicionario_balanceamento.json").write_text(
            json.dumps(status,ensure_ascii=False,indent=2),encoding="utf8")
        raise


def main():
    from argparse import ArgumentParser
    parser=ArgumentParser(description=__doc__)
    parser.add_argument("--execute",action="store_true")
    parser.add_argument("--output-dir",default="qa-dicionario-lob")
    args=parser.parse_args()
    validate_scope_and_dictionary()
    if not args.execute:
        print(json.dumps({"status":"dry-run","projeto":QA_PROJECT,
                          "dicionarios":len(DICTIONARY),
                          "cenarios":[s[0] for s in VARIANTS],
                          "sem_escrita":True}))
        return
    if os.getenv("QA_DICTIONARY_BALANCE_CONFIRM")!=QA_CONFIRM:
        raise RuntimeError("QA_DICTIONARY_BALANCE_CONFIRM=YES_QA_ONLY obrigatorio")
    result=run(config_from_env(),Path(args.output_dir))
    print(json.dumps({k:result[k] for k in ("status","projeto","pacotes_dicionario_completos",
                    "itens_eap_atualizados","pacotes_sem_dono","cronograma_inalterado",
                    "baseline_ativa_preservada")},ensure_ascii=False))


if __name__=="__main__":
    main()
