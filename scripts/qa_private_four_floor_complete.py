#!/usr/bin/env python3
"""Isolated private EAP -> Cronograma -> Gantt/LOB acceptance, four-floor scenario.

The QA project and two historical baselines are intentionally retained in
disposable QA databases. NEVER point to production URLs or databases.
The 100% rule is checked over explicitly declared non-overlapping package
weights; MCP EAP does not natively enforce this contractual budget rule.
"""
from __future__ import annotations

import base64
from datetime import date, timedelta
import hashlib
import io
import json
import math
from pathlib import Path
import uuid
import zipfile

from scripts.qa_three_private_mcps import Mcp, config_from_env

START = date(2026, 11, 9)
FLOORS = ("P01", "P02", "P03", "P04")
# key, title, EAP service type, unit, total quantity, team productivity/day, scope weight (%), stage
PACKAGES = (
    ("mobilizacao", "Mobilizacao e canteiro", "preliminares", "un", 3, 1, 3, "Preparacao"),
    ("fundacao", "Fundacoes", "fundacao", "m³", 120, 20, 8, "Preparacao"),
    ("estrutura", "Estrutura", "estrutura", "m²", 320, 20, 24, "Pavimentos"),
    ("alvenaria", "Alvenaria", "alvenaria", "m²", 400, 25, 16, "Pavimentos"),
    ("hidro", "Instalacoes hidrossanitarias", "hidrossanitaria", "pt", 80, 10, 12, "Pavimentos"),
    ("revestimento", "Revestimentos", "revestimento", "m²", 400, 20, 20, "Pavimentos"),
    ("cobertura", "Cobertura e impermeabilizacao", "cobertura", "m²", 120, 30, 9, "Encerramento"),
    ("comissionamento", "Comissionamento e testes", "acabamento", "un", 4, 2, 5, "Encerramento"),
    ("entrega", "Entrega tecnica", "acabamento", "un", 1, 1, 3, "Encerramento"),
)
P = {x[0]: x for x in PACKAGES}
STAGES = (
    ("Preparacao", "Preparacao e infraestrutura", "infraestrutura"),
    ("Pavimentos", "Pavimentos tipo P01 a P04", "estrutura"),
    ("Encerramento", "Cobertura e encerramento", "acabamento"),
)
# id, package, location, quantity (same engineering unit as EAP package).
SPECS = (
    ("A01", "mobilizacao", "Canteiro", 3),
    ("A02", "fundacao", "Fundacoes", 120),
    *((f"A{i+3:02d}", "estrutura", FLOORS[i], 80) for i in range(4)),
    *((f"A{i+7:02d}", "alvenaria", FLOORS[i], 100) for i in range(4)),
    *((f"A{i+11:02d}", "hidro", FLOORS[i], 20) for i in range(4)),
    *((f"A{i+15:02d}", "revestimento", FLOORS[i], 100) for i in range(4)),
    ("A19", "cobertura", "Cobertura", 120),
    ("A20", "comissionamento", "Sistemas", 4),
    ("A21", "entrega", "Obra", 1),
)
EDGE_NUMBERS = (
    (1,2),(2,3),(3,4),(4,5),(5,6),
    (3,7),(4,8),(7,8),(5,9),(8,9),(6,10),(9,10),
    (7,11),(8,12),(11,12),(9,13),(12,13),(10,14),(13,14),
    (11,15),(12,16),(15,16),(13,17),(16,17),(14,18),(17,18),
    (6,19),(18,20),(19,20),(20,21),
)
EDGES = tuple((f"A{x:02d}", f"A{y:02d}") for x,y in EDGE_NUMBERS)


def validate_declared_scope() -> dict:
    """100% is an external engineering QA rule, NOT an MCP EAP native feature."""
    names = [x[0] for x in PACKAGES]
    assert len(PACKAGES)==9 and len(set(names))==9
    assert sum(x[6] for x in PACKAGES)==100, "Pesos da EAP nao somam 100%"
    assert all(x[3] in {"m²","m³","un","pt"} and x[4]>0 and x[5]>0 and x[6]>0 for x in PACKAGES)
    ids=[x[0] for x in SPECS]
    assert len(ids)==21 and len(set(ids))==21 and len(EDGES)==30
    assert len(EDGES)==len(set(EDGES))
    assert all(a in ids and b in ids and a!=b for a,b in EDGES)
    assert all(x[1] in P and x[3]>0 for x in SPECS)
    for key in names:
        quant=sum(x[3] for x in SPECS if x[1]==key)
        assert quant==P[key][4], f"Quantitativo nao conciliado com EAP: {key}"
    assert set(x[1] for x in SPECS)==set(names)
    durations={a:math.ceil(q/P[package][5]) for a,package,loc,q in SPECS}
    assert all(v>0 for v in durations.values())
    es,ef=calculate_offsets(durations)
    assert max(ef.values())==42, f"Prazo QA esperado 42, recebido {max(ef.values())}"
    revised=dict(durations);revised["A18"]+=2
    revised_es,revised_ef=calculate_offsets(revised)
    assert max(revised_ef.values())==44
    return {"pacotes":9,"peso_escopo_pct":100,"atividades":21,"dependencias":30,
            "duracoes":durations,"inicio_cedo":es,"fim_cedo":ef,
            "revisao_1_duracoes":revised,"revisao_1_inicio_cedo":revised_es,
            "revisao_1_fim_cedo":revised_ef}


def calculate_offsets(durations: dict) -> tuple[dict,dict]:
    predecessors={key:[] for key in durations}
    for a,b in EDGES:
        predecessors[b].append(a)
    es,ef={},{}
    for key in sorted(durations):
        es[key]=max((ef[x] for x in predecessors[key]),default=0)
        ef[key]=es[key]+durations[key]
    return es,ef


def day(offset: float) -> str:
    return (START+timedelta(days=offset)).isoformat()


def validate_zip(b64: str) -> bytes:
    raw=base64.b64decode(b64,validate=True)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names=set(archive.namelist())
        if "xl/workbook.xml" not in names or "[Content_Types].xml" not in names:
            raise AssertionError("Gantt XLSX nao tem estrutura Office Open XML")
    return raw


def run(config: dict, output_dir: Path) -> dict:
    plan=validate_declared_scope()
    clients={name:Mcp(**config[name]) for name in ("eap","cronograma","lob")}
    log=[]
    for name,client in clients.items():
        names=client.connect()
        required={
            "eap":{"criar_projeto","criar_eap_node","get_eap_tree","validar_estrutura","resumo_quantitativos"},
            "cronograma":{"calcular_duracao_com_evidencia","criar_atividade","criar_dependencia",
                          "listar_atividades","calcular_caminho_critico","salvar_baseline",
                          "listar_baselines","comparar_baseline","atualizar_atividade"},
            "lob":{"calcular_linha_balanco","gerar_gantt"},
        }[name]
        if not required.issubset(names):
            raise AssertionError(f"{name}: ferramentas requeridas faltando: {sorted(required-names)}")

    project_id="qa-obra4p-"+uuid.uuid4().hex[:12]
    state={"status":"started","qa_only":True,"project_id":project_id}
    output_dir.mkdir(parents=True,exist_ok=True)
    def call(server,name,args):
        out=clients[server].call(name,args)
        log.append({"motor":server,"ferramenta":name,
                    "sha256":hashlib.sha256(json.dumps(out,sort_keys=True,default=str).encode()).hexdigest()})
        return out
    def check_cpm(result,expected_es,expected_ef,label):
        assert result.get("total_atividades")==21, f"{label}: nao retornou 21 atividades"
        byid={x["id"]:x for x in result["atividades"]}
        assert len(byid)==21
        for key in expected_es:
            item=byid[activity_ids[key]]
            assert (item.get("es"),item.get("ef"))==(expected_es[key],expected_ef[key]),(
                f"{label}: prazo errado {key} {(item.get('es'),item.get('ef'))}")
        assert result["duracao_total_dias"]==max(expected_ef.values())
        assert not result.get("atividades_sem_vinculo"), "Rede possui atividade sem vinculo"
        return byid

    try:
        call("eap","criar_projeto",{"project_id":project_id,"nome":"Edificio QA de 4 pavimentos",
                                   "tipo_obra":"edificio_residencial","area_m2":400})
        roots=call("eap","get_eap_tree",{"project_id":project_id})["raizes"]
        assert len(roots)==1, "EAP deve ter raiz unica gerada por criar_projeto"
        root=roots[0]
        groups={}
        for index,(stage,title,tipo) in enumerate(STAGES):
            groups[stage]=call("eap","criar_eap_node",{
                "project_id":project_id,"parent_id":root["eap_id"],"nome":title,
                "tipo_frente":tipo,"request_id":project_id+f"-grp-{index}"})
        leaves={}
        for i,pack in enumerate(PACKAGES):
            key,title,tipo,unit,quantity,prod,weight,stage=pack
            leaf=call("eap","criar_eap_node",{
                "project_id":project_id,"parent_id":groups[stage]["eap_id"],
                "nome":title,"tipo_frente":tipo,"unidade":unit,"quantidade":quantity,
                "request_id":project_id+f"-pkg-{i}"})
            leaves[key]={"eap_id":leaf["eap_id"],"uid":leaf.get("uid"),"peso":weight}
        tree=call("eap","get_eap_tree",{"project_id":project_id})
        def flatten(nodes):
            return [node for n in nodes for node in ([n]+flatten(n.get("filhos",[])))]
        node_list=flatten(tree["raizes"])
        assert len(node_list)==13 and len(tree["raizes"])==1
        qa_tree=call("eap","validar_estrutura",{"project_id":project_id})
        assert not qa_tree.get("erros") and qa_tree.get("valido") is not False
        qty=call("eap","resumo_quantitativos",{"project_id":project_id})
        assert qty.get("total_grupos",0)>=6
        state.update({"eap_nos":len(node_list),"eap_folhas":len(leaves),
                      "eap_avisos":qa_tree.get("avisos",[]),
                      "eap_quantitativos_grupos":qty["total_grupos"]})
        durations={}
        for key,title,tipo,unit,quantity,productivity,weight,stage in PACKAGES:
            amount=quantity/4 if key in ("estrutura","alvenaria","hidro","revestimento") else quantity
            measured=call("cronograma","calcular_duracao_com_evidencia",{
                "quantidade":amount,"produtividade":productivity,"unidade":unit,
                "unidade_produtividade":unit,"fonte":"Premissa ficticia QA, sem fonte de campo"})
            assert measured["duracaoDias"]==math.ceil(amount/productivity)
            durations[key]=measured["duracaoDias"]

        activity_ids={}
        for idx,(key,package,location,quantity) in enumerate(SPECS):
            unit=P[package][3]
            dur=durations[package]
            assert dur==plan["duracoes"][key]
            if location in FLOORS:
                label=f"{P[package][1]} {location}"
            else:
                label=P[package][1]
            created=call("cronograma","criar_atividade",{
                "project_id":project_id,"eap_ref":leaves[package]["uid"] or leaves[package]["eap_id"],
                "nome":label,"duracao_dias":dur,
                "data_inicio_planejada":day(plan["inicio_cedo"][key]),
                "data_fim_planejada":day(plan["fim_cedo"][key]),
                "request_id":project_id+"-"+key})
            assert created["project_id"]==project_id
            assert created["eap_ref"]==(leaves[package]["uid"] or leaves[package]["eap_id"])
            activity_ids[key]=created["id"]
        for idx,(a,b) in enumerate(EDGES):
            call("cronograma","criar_dependencia",{
                "predecessora_id":activity_ids[a],"sucessora_id":activity_ids[b],
                "tipo":"TI","lag_dias":0,"request_id":project_id+f"-dep-{idx}"})
        actual=call("cronograma","listar_atividades",{"project_id":project_id})
        assert actual["total"]==21
        cpm=call("cronograma","calcular_caminho_critico",{"project_id":project_id})
        cpm_by_id=check_cpm(cpm,plan["inicio_cedo"],plan["fim_cedo"],"Baseline 0")
        state.update({"atividades":21,"dependencias":30,"prazo_bl0_dias":42,
                      "criticas_bl0":sum(bool(x.get("critica")) for x in cpm_by_id.values())})
        original=call("cronograma","salvar_baseline",{
            "project_id":project_id,"nome":"QA Baseline 0 - Escopo aprovado"})
        baseline_id=original["id"]
        initial_cmp=call("cronograma","comparar_baseline",{"baseline_id":baseline_id})
        assert len(initial_cmp["comparacao"])==21
        assert all(x.get("desvio_duracao_dias") in (0,0.0) for x in initial_cmp["comparacao"])

        lob=call("lob","calcular_linha_balanco",{
            "atividades":[{"nome":P[k][1],"tempo_unitario":durations[k],"numero_equipes":1,
                           "pulmao_dias":0} for k in ("estrutura","alvenaria","hidro","revestimento")],
            "unidades":list(FLOORS),"data_inicio":day(9)})
        assert lob.get("duracao_total_dias")==30
        lob_units={(s["nome"],unit["unidade"]):unit for s in lob["atividades"]
                   for unit in s["unidades"]}
        matched=[]
        for key,package,local,quantity in SPECS:
            if local not in FLOORS:continue
            unit=lob_units[(P[package][1],local)]
            a=cpm_by_id[activity_ids[key]]
            same=(a["es"]-9==unit["inicio_dia"] and a["ef"]-9==unit["fim_dia"])
            matched.append({"atividade":key,"local":local,"coincide":same})
            assert same, f"CPM x LOB divergiram: {key} / {local}"
        assert len(matched)==16

        def export_gantt(label,rows_map,filename):
            data=[]
            for key,package,local,quantity in SPECS:
                x=rows_map[activity_ids[key]]
                data.append({
                    "nome":P[package][1]+(f" {local}" if local in FLOORS else ""),
                    "secao":P[package][7],"data_inicio":day(x["es"]),
                    "data_fim_planejada":day(x["ef"]),"progresso":0,
                    "critico":bool(x.get("critica"))})
            result=call("lob","gerar_gantt",{
                "project_name":project_id+"_"+label,"atividades":data,"tema":"slate"})
            data_bytes=validate_zip(result["xlsx_base64"])
            (output_dir/filename).write_bytes(data_bytes)
            return {"arquivo":filename,"tamanho_bytes":len(data_bytes),
                    "sha256":hashlib.sha256(data_bytes).hexdigest()}
        gantt0=export_gantt("BL0",cpm_by_id,"gantt_obra4p_baseline_0.xlsx")

        revised_dur=plan["revisao_1_duracoes"]
        revised_es=plan["revisao_1_inicio_cedo"]
        revised_ef=plan["revisao_1_fim_cedo"]
        changed=call("cronograma","atualizar_atividade",{
            "atividade_id":activity_ids["A18"],"duracao_dias":7,
            "data_fim_planejada":day(revised_ef["A18"])})
        assert changed.get("duracao_dias")==7
        revision=call("cronograma","calcular_caminho_critico",{"project_id":project_id})
        rev_by_id=check_cpm(revision,revised_es,revised_ef,"Revisao 1")
        # Update planned dates for every displaced downstream activity, so
        # baseline comparisons capture real date deviations as well as duration.
        for key in revised_es:
            if (revised_es[key],revised_ef[key])==(plan["inicio_cedo"][key],plan["fim_cedo"][key]):
                continue
            call("cronograma","atualizar_atividade",{
                "atividade_id":activity_ids[key],
                "data_inicio_planejada":day(revised_es[key]),
                "data_fim_planejada":day(revised_ef[key])})
        delta=call("cronograma","comparar_baseline",{"baseline_id":baseline_id})
        assert len(delta["comparacao"])==21
        changed_duration=[x for x in delta["comparacao"] if x.get("desvio_duracao_dias") not in (0,0.0)]
        assert len(changed_duration)==1
        assert changed_duration[0]["atividade_id"]==activity_ids["A18"]
        assert changed_duration[0]["desvio_duracao_dias"]==2
        changed_dates=[x for x in delta["comparacao"] if
                       x.get("data_fim_planejada_baseline")!=x.get("data_fim_planejada_atual")]
        assert len(changed_dates)>=3
        current_base=call("cronograma","salvar_baseline",{
            "project_id":project_id,"nome":"QA Baseline 1 - Revisao +2 dias"})
        history=call("cronograma","listar_baselines",{"project_id":project_id})
        assert history["total"]==2
        assert sum(bool(x.get("ativa")) for x in history["baselines"])==1
        assert next(x for x in history["baselines"] if x["id"]==current_base["id"])["ativa"]
        cmp1=call("cronograma","comparar_baseline",{"baseline_id":current_base["id"]})
        assert len(cmp1["comparacao"])==21
        assert all(x.get("desvio_duracao_dias") in (0,0.0) for x in cmp1["comparacao"])
        gantt1=export_gantt("REV1",rev_by_id,"gantt_obra4p_revisao_1.xlsx")
        report={
            **state,"status":"passed","evidencia":"Execucao autenticada em 3 MCPs QA",
            "regra_100_metodo":"externa: pesos declarados e conciliacao folha/atividade; nao implementada no MCP EAP",
            "peso_pacotes_percentual":100,"peso_por_pacote":{p[0]:p[6] for p in PACKAGES},
            "prazo_rev1_dias":44,"atraso_critico_dias":2,
            "baseline_0":baseline_id,"baseline_1":current_base["id"],
            "baseline_historicas":1,"baseline_ativas":1,
            "CPM_LOB_conciliadas":sum(x["coincide"] for x in matched),
            "CPM_LOB_total":len(matched),
            "lob_espera_instalacoes_dias":next(x["espera_total_dias"] for x in lob["atividades"]
                                             if x["nome"]==P["hidro"][1]),
            "revisao_atividades_duracao_alterada":[x["nome"] for x in changed_duration],
            "revisao_atividades_datas_alteradas":[x["nome"] for x in changed_dates],
            "pacotes":[{"key":p[0],"nome":p[1],"unidade":p[3],
                         "quantidade":p[4],"produtividade_por_dia":p[5],
                         "peso_percentual":p[6],"eap_ref":leaves[p[0]]["eap_id"]} for p in PACKAGES],
            "atividades_modelo":[{"codigo":key,"nome":P[package][1],"local":loc,
                                  "quantidade":q,"duracao_dias":plan["duracoes"][key],
                                  "eap_ref":leaves[package]["eap_id"],
                                  "es":plan["inicio_cedo"][key],"ef":plan["fim_cedo"][key],
                                  "es_rev1":revised_es[key],"ef_rev1":revised_ef[key],
                                  "critica":bool(cpm_by_id[activity_ids[key]].get("critica")),
                                  "id_privado":activity_ids[key]} for key,package,loc,q in SPECS],
            "vinculos":[{"predecessora":a,"sucessora":b} for a,b in EDGES],
            "lob_atividades":lob["atividades"],
            "comparacao_cpm_lob":matched,
            "gantt_bl0":gantt0,"gantt_rev1":gantt1,"chamadas":log,
            "qa_persistencia":"Dados QA retidos para auditoria; nenhuma exclusao automatica",
        }
        (output_dir/"relatorio_obra4p_privada.json").write_text(
            json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding="utf8")
        return report
    except Exception as exc:
        (output_dir/"falha_obra4p_privada.json").write_text(
            json.dumps({**state,"status":"failed","erro":f"{type(exc).__name__}: {exc}",
                        "ultimas_chamadas":log[-5:]},ensure_ascii=False,indent=2),encoding="utf8")
        raise


def main():
    from argparse import ArgumentParser
    parser=ArgumentParser(description=__doc__)
    parser.add_argument("--execute",action="store_true")
    parser.add_argument("--output-dir",default="qa-obra4p-private")
    args=parser.parse_args()
    if not args.execute:
        print(json.dumps({"status":"dry-run","plan":{k:v for k,v in validate_declared_scope().items()
                                                     if k not in ("duracoes","inicio_cedo","fim_cedo",
                                                     "revisao_1_duracoes","revisao_1_inicio_cedo","revisao_1_fim_cedo")}}))
        return 0
    config=config_from_env()  # exact QA-only host and secret guards from proven runner.
    result=run(config,Path(args.output_dir))
    print(json.dumps({k:result[k] for k in (
        "status","project_id","eap_nos","eap_folhas","atividades","dependencias",
        "prazo_bl0_dias","prazo_rev1_dias","CPM_LOB_conciliadas",
        "baseline_historicas","baseline_ativas","gantt_bl0","gantt_rev1")},ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
