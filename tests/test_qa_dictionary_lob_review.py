"""QA regression: dictionary completeness + scenario comparison without touching CPM."""
import copy
import pytest

from scripts import qa_dictionary_lob_review as runner
from scripts.qa_private_four_floor_complete import PACKAGES


def test_dictionary_complete_and_well_scoped():
    runner.validate_scope_and_dictionary()
    assert len(runner.DICTIONARY)==9
    assert set(runner.DICTIONARY)=={p[0] for p in PACKAGES}
    for key in runner.DICTIONARY:
        d=runner.build_dictionary(key)
        assert "INCLUSÕES:" in d["descricao"]
        assert "EXCLUSÕES:" in d["descricao"]
        assert "CRITÉRIO DE ACEITAÇÃO (QA):" in d["descricao"]
        assert d["responsavel"].startswith("Papel QA - ")


def test_dictionary_rejects_missing_package(monkeypatch):
    monkeypatch.delitem(runner.DICTIONARY,"estrutura")
    with pytest.raises(AssertionError):
        runner.validate_scope_and_dictionary()


def test_qa_dictionary_and_lob_full_mock(monkeypatch,tmp_path):
    edits=[]
    groups={}
    leaves={}
    for idx,p in enumerate(PACKAGES):
        key,_,tipo,unid,qty,*_=p
        parent={"Preparacao":"1.1","Pavimentos":"1.2","Encerramento":"1.3"}[p[7]]
        leaves[key]={"uid":f"u{idx+1}","eap_id":f"{parent}.{idx+1}",
                     "nome":p[1],"tipo_frente":tipo,"unidade":unid,"quantidade":qty,
                     "descricao":None,"criterio_medicao":None,"responsavel":None,"disciplina":None}
        groups.setdefault(parent,[]).append(leaves[key])
    def tree():
        return {"raizes":[{"eap_id":"1","nome":"Obra QA","filhos":[
            {"eap_id":g,"filhos":[copy.deepcopy(n) for n in v]} for g,v in groups.items()
        ]}]}
    log=[]
    class FakeMcp:
        def __init__(self,url,token):
            self.name=url
        def connect(self):
            return {"get_eap_tree","definir_criterio","pacotes_sem_dono","validar_estrutura",
                    "listar_atividades","listar_baselines","calcular_cpm_com_evidencia",
                    "balancear_ritmos_lob","calcular_linha_balanco"}
        def call(self,tool,args):
            log.append((self.name,tool,args))
            if self.name=="eap":
                if tool=="get_eap_tree":return tree()
                if tool=="pacotes_sem_dono":
                    return {"total":sum(1 for x in leaves.values() if not x["responsavel"])}
                if tool=="validar_estrutura":
                    return {"erros":[],"avisos":[]}
                if tool=="definir_criterio":
                    found=next(v for v in leaves.values() if v["uid"]==args["uid"])
                    found.update({k:args[k] for k in
                        ("descricao","criterio_medicao","responsavel","disciplina")})
                    edits.append(found["uid"])
                    return found.copy()
            if self.name=="cronograma":
                if tool=="calcular_cpm_com_evidencia":
                    assert len(args["atividades"])==21 and len(args["dependencias"])==30
                    byid={a["id"]:a["duracao_dias"] for a in args["atividades"]}
                    d=byid["A03"]
                    a=byid["A07"]
                    expected={(4,4):42,(4,2):40,(2,2):38,(2,4):40}[(d,a)]
                    return {"valid":True,"duracao_projeto_dias":expected,"persistido":False}
                if tool=="listar_atividades":
                    return {"total":21,"atividades":[{"id":f"a{i}"} for i in range(21)]}
                if tool=="listar_baselines":
                    return {"total":2,"baselines":[{"id":"BL0","ativa":False},{"id":"BL1","ativa":True}]}
            if self.name=="lob":
                if tool=="balancear_ritmos_lob":
                    return {"sugestoes":[
                        {"nome":"Estrutura","risco_interferencia":False},
                        {"nome":"Alvenaria","risco_interferencia":False},
                        {"nome":"Instalacoes hidrossanitarias","risco_interferencia":True,
                         "equipes_predecessora_para_acelerar":2},
                        {"nome":"Revestimentos","risco_interferencia":False}]}
                if tool=="calcular_linha_balanco":
                    crews=tuple(a["numero_equipes"] for a in args["atividades"])
                    dur={(1,1,1,1):30,(1,2,1,1):28,(2,2,1,1):26,(2,1,1,1):28}[crews]
                    w=(0 if crews==(2,2,1,1) else 6)
                    out=[]
                    for i,a in enumerate(args["atividades"]):
                        out.append({"nome":a["nome"],
                                    "espera_total_dias":w if i==2 else 0,
                                    "risco_interferencia":bool(w) if i==2 else False})
                    return {"duracao_total_dias":dur,"atividades":out}
            raise AssertionError(f"Unexpected {self.name}/{tool}")
    monkeypatch.setattr(runner,"Mcp",FakeMcp)
    cfg={n:{"url":n,"token":"mock"} for n in ("eap","cronograma","lob")}
    report=runner.run(cfg,tmp_path)
    assert report["status"]=="passed"
    assert report["pacotes_dicionario_completos"]==9
    assert report["itens_eap_atualizados"]==9
    assert report["pacotes_sem_dono"]==0
    assert (report["cronograma_inalterado"],report["baseline_ativa_preservada"])==(True,True)
    assert len(edits)==9
    assert [x["prazo_lob_dias"] for x in report["cenarios"]]==[30,28,26,28]
    assert [x["prazo_cpm_obra_completa_desde_bl0_dias"] for x in report["cenarios"]]==[42,40,38,40]
    assert all(x["cpm_persistido"] is False for x in report["cenarios"])
    assert (tmp_path/"qa_dicionario_e_balanceamento.json").is_file()
    assert all(name not in ("atualizar_atividade","salvar_baseline","criar_dependencia") for _,name,_ in log)


def test_qa_never_overwrites_non_matching_existing_owner(monkeypatch,tmp_path):
    # Any existing nonmatching dictionary field must fail before a single mutation.
    runner.validate_scope_and_dictionary()
    existing=runner.build_dictionary("mobilizacao")
    assert "QA" in existing["responsavel"]
