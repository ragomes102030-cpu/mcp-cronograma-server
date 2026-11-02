#!/usr/bin/env python3
"""QA-only private MCP roundtrip. Never points at production endpoints.

Run: QA_PRIVATE_E2E_CONFIRM=YES_QA_ONLY python scripts/qa_three_private_mcps.py --execute
Requires three QA-only HTTPS URLs, three private MCP bearer tokens, and no production DB.
This runner intentionally RETAINS the generated QA-only project because the private
Cronograma MCP has no project/baseline deletion API. The output is its audit ledger.
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid
from urllib.parse import urlparse
from urllib.request import Request, urlopen

CONFIRM = "YES_QA_ONLY"
TARGETS = {
    "eap": ("QA_EAP_MCP_URL", "QA_EAP_MCP_TOKEN", "arquimedes-eap-private-qa-20261102.vercel.app"),
    "cronograma": ("QA_CRONOGRAMA_MCP_URL", "QA_CRONOGRAMA_MCP_TOKEN", "arquimedes-cronograma-qa-runner.vercel.app"),
    "lob": ("QA_LOB_MCP_URL", "QA_LOB_MCP_TOKEN", "arquimedes-lob-private-qa-20261102.vercel.app"),
}
DATE_START = "2026-11-09"


def host_guard(name: str, raw: str) -> str:
    """Fail closed: only the three exact Vercel QA project domains, no redirects."""
    u = urlparse(raw.strip())
    approved_host = TARGETS[name][2]
    hostname = (u.hostname or "").lower()
    if (u.scheme != "https" or u.username or u.password or u.port
            or u.query or u.fragment or not hostname.endswith(".vercel.app")
            or hostname != approved_host or u.path.rstrip("/") != "/mcp"):
        raise ValueError(f"{name}: URL nao corresponde ao deployment privado QA aprovado")
    return raw.rstrip("/")


def config_from_env() -> dict:
    if os.getenv("QA_PRIVATE_E2E_CONFIRM") != CONFIRM:
        raise ValueError("QA_PRIVATE_E2E_CONFIRM deve ser YES_QA_ONLY")
    config = {}
    for name, (urlkey, tokenkey, _) in TARGETS.items():
        url, token = os.getenv(urlkey, ""), os.getenv(tokenkey, "")
        config[name] = {"url": host_guard(name, url), "token": token}
        if not token or len(token.strip()) < 24:
            raise ValueError(f"{name}: token QA privado nao configurado")
    if len(set(x["url"] for x in config.values())) != 3:
        raise ValueError("MCPs QA devem ter endpoints distintos")
    return config


class Mcp:
    def __init__(self, url: str, token: str):
        self.url = url
        self.token = token
        self.next_id = 0

    def request(self, method: str, params: dict | None = None, *, notify=False) -> dict:
        self.next_id += 1
        payload = {"jsonrpc": "2.0", "method": method}
        if not notify:
            payload["id"] = self.next_id
        if params is not None:
            payload["params"] = params
        encoded = json.dumps(payload, ensure_ascii=False).encode()
        req = Request(self.url, encoded, method="POST", headers={
            "authorization": "Bearer " + self.token,
            "accept": "application/json, text/event-stream",
            "content-type": "application/json",
            "mcp-protocol-version": "2025-06-18",
        })
        # Never automatically follow redirects with a credential-bearing request.
        from urllib.request import build_opener, HTTPRedirectHandler
        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        opener = build_opener(NoRedirect)
        with opener.open(req, timeout=40) as response:
            if response.status not in (200, 202):
                raise RuntimeError(f"{method}: resposta HTTP {response.status}")
            raw = response.read(3_000_000).decode("utf8")
        if notify:
            return {}
        if raw.startswith("event:") or raw.startswith("data:"):
            rows = [line[5:].strip() for line in raw.splitlines() if line.startswith("data:")]
            raw = rows[-1] if rows else raw
        parsed = json.loads(raw)
        if parsed.get("error"):
            raise RuntimeError(f"{method}: erro JSON-RPC: {parsed['error'].get('message', 'unknown')}")
        return parsed.get("result") or {}

    def connect(self):
        data = self.request("initialize", {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "arquimedes-private-qa", "version": "1.0.0"},
        })
        if not data.get("serverInfo"):
            raise RuntimeError("initialize sem identidade de servidor")
        self.request("notifications/initialized", {}, notify=True)
        tools = self.request("tools/list", {}).get("tools", [])
        return {t["name"] for t in tools}

    def call(self, name: str, args: dict) -> dict:
        response = self.request("tools/call", {"name": name, "arguments": args})
        if response.get("isError"):
            raise RuntimeError(f"{name}: MCP sinalizou isError")
        data = response.get("structuredContent")
        if not isinstance(data, dict):
            cells = response.get("content") or []
            data = json.loads(next((x["text"] for x in cells if x.get("type") == "text"), "{}"))
        if isinstance(data, dict) and set(data) == {"result"} and isinstance(data["result"], dict):
            data = data["result"]
        if not isinstance(data, dict) or data.get("isError") or data.get("erro"):
            raise RuntimeError(f"{name}: resultado de negocio invalido: {str(data)[:180]}")
        return data


def run(config: dict, *, export_dir: Path) -> dict:
    clients = {name: Mcp(**v) for name, v in config.items()}
    audit = []
    project_id = "qa-integracao-" + uuid.uuid4().hex[:12]
    def invoke(server: str, tool: str, args: dict):
        result = clients[server].call(tool, args)
        audit.append({"motor": server, "ferramenta": tool,
                      "resultado_sha256": hashlib.sha256(json.dumps(result, ensure_ascii=False,
                                          sort_keys=True).encode()).hexdigest(),
                      "status": "aprovado"})
        return result

    for name, client in clients.items():
        tools = client.connect()
        must = {"eap": {"criar_projeto", "criar_eap_node", "get_eap_tree", "validar_estrutura"},
                "cronograma": {"criar_atividade", "criar_dependencia", "listar_atividades",
                                "calcular_caminho_critico", "salvar_baseline", "listar_baselines", "comparar_baseline"},
                "lob": {"calcular_linha_balanco", "gerar_gantt"}}[name]
        if not must.issubset(tools):
            raise RuntimeError(f"{name}: ferramentas privadas faltando: {sorted(must-tools)}")

    # One unique QA project in the isolated databases. No 'default' identifier.
    invoke("eap", "criar_projeto", {"project_id": project_id, "nome": "QA Integracao Tres MCPs"})
    root = invoke("eap", "criar_eap_node", {
        "project_id": project_id, "nome": "Obra QA", "tipo_frente": "geral",
        "request_id": project_id + "-root"})
    root_id = root["eap_id"]
    group = invoke("eap", "criar_eap_node", {
        "project_id": project_id, "nome": "Pavimentos tipo", "parent_id": root_id,
        "tipo_frente": "estrutura", "request_id": project_id + "-group"})
    leaves = {}
    for key, label, unit, qty in [("est", "Estrutura", "m2", 160), ("alv", "Alvenaria", "m2", 200)]:
        item = invoke("eap", "criar_eap_node", {
            "project_id": project_id, "parent_id": group["eap_id"], "nome": label,
            "tipo_frente": "estrutura" if key=="est" else "vedacao",
            "unidade": unit, "quantidade": qty,
            "request_id": project_id+"-"+key})
        leaves[key] = item.get("uid") or item["eap_id"]
    tree = invoke("eap", "get_eap_tree", {"project_id": project_id})
    assert len(tree.get("raizes", [])) == 1
    structure = invoke("eap", "validar_estrutura", {"project_id": project_id})
    # Validation response may contain semantic warnings; do not equate warnings with errors.
    if structure.get("erros") or structure.get("valido") is False:
        raise AssertionError("EAP QA possui erros estruturais")

    activity_specs = [
        ("pre", "Mobilizacao", root.get("uid") or root_id, 2, "Preparacao"),
        ("est1", "Estrutura P01", leaves["est"], 4, "P01"),
        ("est2", "Estrutura P02", leaves["est"], 4, "P02"),
        ("alv1", "Alvenaria P01", leaves["alv"], 5, "P01"),
        ("alv2", "Alvenaria P02", leaves["alv"], 5, "P02"),
    ]
    # Explicit planned dates: baseline must snapshot meaningful start/finish
    # values, not five null dates. End is exclusive for the QA comparison.
    expected_offsets = {"pre": (0, 2), "est1": (2, 6), "est2": (6, 10),
                        "alv1": (6, 11), "alv2": (11, 16)}
    created = {}
    for key, label, ref, duration, _ in activity_specs:
        item = invoke("cronograma", "criar_atividade", {
            "project_id": project_id, "eap_ref": ref, "nome": label,
            "duracao_dias": duration,
            "data_inicio_planejada": (date.fromisoformat(DATE_START)+timedelta(days=expected_offsets[key][0])).isoformat(),
            "data_fim_planejada": (date.fromisoformat(DATE_START)+timedelta(days=expected_offsets[key][1])).isoformat(),
            "request_id": project_id+"-"+key})
        if item.get("project_id") != project_id or item.get("eap_ref") != ref:
            raise AssertionError("Atividade sem vínculo EAP/projeto esperado")
        created[key] = item["id"]
    pairs = [("pre","est1"), ("est1","est2"), ("est1","alv1"),
             ("est2","alv2"), ("alv1","alv2")]
    for idx, (a,b) in enumerate(pairs):
        invoke("cronograma", "criar_dependencia", {
            "predecessora_id": created[a], "sucessora_id": created[b],
            "tipo": "TI", "lag_dias": 0, "request_id":project_id+f"-dep-{idx}"})
    read_back = invoke("cronograma", "listar_atividades", {"project_id": project_id})
    if read_back.get("total") != 5:
        raise AssertionError("Read-after-write retornou contagem diferente")
    calc = invoke("cronograma", "calcular_caminho_critico", {"project_id": project_id})
    if calc.get("total_atividades") != 5 or calc.get("duracao_total_dias") != 16:
        raise AssertionError("CPM privado divergente da rede de referência (16 dias)")
    for key, _, _, _, _ in activity_specs:
        row = next(x for x in calc["atividades"] if x["id"] == created[key])
        actual = (row.get("ES", row.get("es")), row.get("EF", row.get("ef")))
        if actual != expected_offsets[key]:
            raise AssertionError(f"CPM privado divergiu dos intervalos: {key} {actual}")
    base = invoke("cronograma", "salvar_baseline", {"project_id": project_id, "nome": "QA Baseline 0"})
    base_list = invoke("cronograma", "listar_baselines", {"project_id": project_id})
    if base_list.get("total") != 1 or not base.get("id"):
        raise AssertionError("Baseline não persistiu no banco QA")
    cmp_baseline = invoke("cronograma", "comparar_baseline", {"baseline_id": base["id"]})
    compare_rows = cmp_baseline.get("comparacao") or []
    if len(compare_rows) != 5 or any(
        x.get("desvio_duracao_dias") not in (0, 0.0) for x in compare_rows
    ):
        raise AssertionError("Baseline QA incompleta ou com desvio inesperado")
    lob = invoke("lob", "calcular_linha_balanco", {
        "atividades": [{"nome": "Estrutura", "tempo_unitario": 4, "numero_equipes": 1},
                       {"nome": "Alvenaria", "tempo_unitario": 5, "numero_equipes": 1}],
        "unidades": ["P01","P02"], "data_inicio": (date.fromisoformat(DATE_START)+timedelta(days=2)).isoformat(),
    })
    if lob.get("duracao_total_dias") != 14:
        raise AssertionError("LOB privada não corresponde aos 14 dias pós-mobilização")
    # Compare each repeated activity against private CPM, after mobilization
    # offsets. This is an independently checked cross-engine contract.
    by_id = {row["id"]: row for row in calc["atividades"]}
    lob_units = {
        (service.get("nome"), unit.get("unidade")): unit
        for service in lob.get("atividades", [])
        for unit in service.get("unidades", [])
    }
    comparisons = []
    for key, name, location in [
        ("est1", "Estrutura", "P01"), ("est2", "Estrutura", "P02"),
        ("alv1", "Alvenaria", "P01"), ("alv2", "Alvenaria", "P02")
    ]:
        cpm_task = by_id[created[key]]
        lob_task = lob_units.get((name, location))
        if not lob_task:
            raise AssertionError(f"LOB sem tarefa {name}/{location}")
        start_cpm = cpm_task.get("ES", cpm_task.get("es"))
        finish_cpm = cpm_task.get("EF", cpm_task.get("ef"))
        if start_cpm is None or finish_cpm is None:
            raise AssertionError("CPM sem datas cedo")
        equal = (abs((start_cpm - 2) - lob_task["inicio_dia"]) < 1e-6
                 and abs((finish_cpm - 2) - lob_task["fim_dia"]) < 1e-6)
        comparisons.append({"servico": name, "local": location, "coincide": equal})
        if not equal:
            raise AssertionError(f"CPM/LOB divergem na tarefa {name}/{location}")
    rows = []
    for a in calc["atividades"]:
        start = date.fromisoformat(DATE_START)+timedelta(days=a["ES"] if "ES" in a else a["es"])
        finish = date.fromisoformat(DATE_START)+timedelta(days=a["EF"] if "EF" in a else a["ef"])
        match = next(v for v in activity_specs if created[v[0]] == a["id"])
        rows.append({"nome": match[1], "secao": "QA", "data_inicio":start.isoformat(),
                     "data_fim_planejada":finish.isoformat(),"progresso":0,
                     "critico":bool(a.get("critica", a.get("critico", False)))})
    gantt = invoke("lob", "gerar_gantt", {
        "project_name": project_id, "atividades": rows, "tema": "slate"})
    import base64
    exported = base64.b64decode(gantt["xlsx_base64"])
    if exported[:2] != b"PK":
        raise AssertionError("Gantt gerado não é arquivo XLSX ZIP válido")
    export_dir.mkdir(parents=True, exist_ok=True)
    (export_dir / "gantt_qa_privado.xlsx").write_bytes(exported)
    report = {
        "status": "passed", "project_id": project_id,
        "qa_only": True, "persistent_test_data_retained": True,
        "reason": "Cronograma privado nao possui delecao segura de baseline/projeto",
        "eap_nodes": 4, "activities": 5, "dependencies": 5,
        "cpm_days": 16, "lob_days_after_mobilization": 14,
        "baseline_saved": True, "gantt_bytes": len(exported),
        "cpm_lob_comparisons": comparisons, "calls": audit,
    }
    (export_dir / "relatorio_qa_privado.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Enable QA writes after all guards")
    parser.add_argument("--output-dir", default="qa-three-mcp-results")
    args = parser.parse_args(argv)
    if not args.execute:
        print(json.dumps({"status":"dry-run", "requires":"--execute + QA_PRIVATE_E2E_CONFIRM",
                          "scope":"ONLY 3 explicitly named QA Vercel projects",
                          "retention":"project/baseline retained inside disposable QA DB"},indent=2))
        return 0
    config = config_from_env()
    result = run(config, export_dir=Path(args.output_dir))
    print(json.dumps({k:v for k,v in result.items() if k!="calls"},ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
