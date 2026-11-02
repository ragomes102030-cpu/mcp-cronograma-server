"""Safety and full-flow tests for disposable three-private-MCP acceptance runner.

These tests use in-memory fakes. They do NOT substitute for live authenticated QA.
"""
import base64
import pytest

from scripts import qa_three_private_mcps as qa


def test_qa_guards_deny_production_and_untrusted_urls(monkeypatch):
    bad = [
        "https://arquimedes-mcp-eap.vercel.app/mcp",
        "https://arquimedes-eap-private-qa-20261102.vercel.app/public-mcp",
        "http://arquimedes-eap-private-qa-20261102-x.vercel.app/mcp",
        "https://arquimedes-eap-private-qa-20261102-x.vercel.app.evil.test/mcp",
        "https://user:pass@arquimedes-eap-private-qa-20261102-x.vercel.app/mcp",
        "https://arquimedes-eap-private-qa-20261102-x.vercel.app/mcp?token=bad",
        "https://arquimedes-eap-private-qa-20261102-x.vercel.app/anything",
    ]
    for url in bad:
        with pytest.raises(ValueError):
            qa.host_guard("eap", url)
    assert qa.host_guard(
        "eap", "https://arquimedes-eap-private-qa-20261102-x.vercel.app/mcp/"
    ).endswith("/mcp")
    monkeypatch.delenv("QA_PRIVATE_E2E_CONFIRM", raising=False)
    with pytest.raises(ValueError, match="YES_QA_ONLY"):
        qa.config_from_env()


def test_no_execution_without_flag(capsys, monkeypatch):
    monkeypatch.delenv("QA_PRIVATE_E2E_CONFIRM", raising=False)
    assert qa.main([]) == 0
    assert '"status": "dry-run"' in capsys.readouterr().out


def test_private_integrated_flow_with_qa_fakes(monkeypatch, tmp_path):
    """One test project flows from EAP into Cronograma and Gantt/LOB."""
    history = []
    counters = {"eap": 0, "cronograma": 0}

    class FakeMcp:
        def __init__(self, url, token):
            self.server = url
        def connect(self):
            return {
                "criar_projeto","criar_eap_node","get_eap_tree","validar_estrutura",
                "criar_atividade","criar_dependencia","listar_atividades",
                "calcular_caminho_critico","salvar_baseline","listar_baselines","comparar_baseline",
                "calcular_linha_balanco","gerar_gantt",
            }
        def call(self, name, args):
            history.append((self.server,name,args))
            if name=="criar_projeto":
                return {"project_id":args["project_id"]}
            if name=="criar_eap_node":
                counters["eap"]+=1
                num=counters["eap"]
                return {"eap_id":["1","1.1","1.1.1","1.1.2"][num-1],"uid":f"qa-uid-{num}"}
            if name=="get_eap_tree":
                return {"raizes":[{"eap_id":"1"}]}
            if name=="validar_estrutura":
                return {"valido":True,"erros":[]}
            if name=="criar_atividade":
                counters["cronograma"]+=1
                return {"id":f"act{counters['cronograma']}", "project_id":args["project_id"],
                        "eap_ref":args["eap_ref"]}
            if name=="criar_dependencia":
                return {"id":"dep-"+args["request_id"]}
            if name=="listar_atividades":
                return {"total":5}
            if name=="calcular_caminho_critico":
                offsets=[(0,2),(2,6),(6,10),(6,11),(11,16)]
                return {"total_atividades":5,"duracao_total_dias":16,
                        "atividades":[{"id":f"act{i+1}","ES":a,"EF":b,"critica":True}
                                      for i,(a,b) in enumerate(offsets)]}
            if name=="salvar_baseline":
                return {"id":"baseline-qa"}
            if name=="listar_baselines":
                return {"total":1}
            if name=="comparar_baseline":
                return {"comparacao":[{"desvio_duracao_dias":0} for _ in range(5)]}
            if name=="calcular_linha_balanco":
                return {"duracao_total_dias":14,"atividades":[
                    {"nome":"Estrutura","unidades":[
                        {"unidade":"P01","inicio_dia":0,"fim_dia":4},
                        {"unidade":"P02","inicio_dia":4,"fim_dia":8}]},
                    {"nome":"Alvenaria","unidades":[
                        {"unidade":"P01","inicio_dia":4,"fim_dia":9},
                        {"unidade":"P02","inicio_dia":9,"fim_dia":14}]}
                ]}
            if name=="gerar_gantt":
                return {"xlsx_base64":base64.b64encode(b"PK\\x03\\x04fake-qa-zip").decode()}
            raise AssertionError(name)
    monkeypatch.setattr(qa,"Mcp",FakeMcp)
    cfg={n:{"url":n,"token":"test-only"} for n in qa.TARGETS}
    result=qa.run(cfg,export_dir=tmp_path)
    assert result["status"]=="passed"
    assert result["persistent_test_data_retained"] is True
    assert (result["eap_nodes"],result["activities"],result["dependencies"])==(4,5,5)
    assert result["cpm_days"]==16 and result["lob_days_after_mobilization"]==14
    assert len(result["cpm_lob_comparisons"])==4
    assert all(row["coincide"] for row in result["cpm_lob_comparisons"])
    assert (tmp_path/"relatorio_qa_privado.json").is_file()
    assert (tmp_path/"gantt_qa_privado.xlsx").read_bytes().startswith(b"PK")
    tools=[name for _,name,_ in history]
    assert tools.index("criar_eap_node")<tools.index("criar_atividade")
    assert tools.index("calcular_caminho_critico")<tools.index("gerar_gantt")
    assert all(args.get("project_id","")!="default" for _,_,args in history)
