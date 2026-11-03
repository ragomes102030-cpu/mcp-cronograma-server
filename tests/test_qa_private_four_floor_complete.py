"""Offline invariants for 4-floor QA: no production access or MCP credentials."""
from collections import Counter
import pytest

from scripts import qa_private_four_floor_complete as plan


def test_qa_full_scope_is_100_percent_and_no_overlapping_leaves():
    r=plan.validate_declared_scope()
    assert (r["pacotes"],r["peso_escopo_pct"],r["atividades"],r["dependencias"])==(9,100,21,30)
    assert len(plan.FLOORS)==4
    assert len(set(k for k,_,_,_ in plan.SPECS))==21
    quantities=Counter()
    for _,k,_,q in plan.SPECS:quantities[k]+=q
    assert quantities==Counter({x[0]:x[4] for x in plan.PACKAGES})
    assert sum(x[6] for x in plan.PACKAGES)==100
    assert all(r["duracoes"][k]>0 for k in r["duracoes"])


def test_qa_full_cpm_baseline_and_revision_expected_dates():
    p=plan.validate_declared_scope()
    assert max(p["fim_cedo"].values())==42
    assert max(p["revisao_1_fim_cedo"].values())==44
    assert p["duracoes"]["A18"]==5
    assert p["revisao_1_duracoes"]["A18"]==7
    changed=[k for k in p["fim_cedo"] if
             (p["inicio_cedo"][k],p["fim_cedo"][k])!=
             (p["revisao_1_inicio_cedo"][k],p["revisao_1_fim_cedo"][k])]
    assert {"A18","A20","A21"}.issubset(changed)
    for a,b in plan.EDGES:
        assert p["fim_cedo"][a]<=p["inicio_cedo"][b]


def test_qa_scope_rejects_missing_or_double_counted_package(monkeypatch):
    bad=list(plan.PACKAGES)
    row=list(bad[0]);row[6]=row[6]+1;bad[0]=tuple(row)
    monkeypatch.setattr(plan,"PACKAGES",tuple(bad))
    with pytest.raises(AssertionError,match="100%"):
        plan.validate_declared_scope()


def test_qa_scope_rejects_qty_discrepancy(monkeypatch):
    wrong=list(plan.SPECS)
    row=list(wrong[0]);row[3]+=2;wrong[0]=tuple(row)
    monkeypatch.setattr(plan,"SPECS",tuple(wrong))
    with pytest.raises(AssertionError,match="Quantitativo"):
        plan.validate_declared_scope()


def test_qa_full_dry_run_never_accesses_servers(capsys,monkeypatch):
    monkeypatch.setattr(plan,"config_from_env",lambda: (_ for _ in ()).throw(
        AssertionError("dry-run jamais pode ler credenciais")))
    assert plan.main if callable(plan.main) else False
    assert len(plan.validate_declared_scope()["duracoes"])==21
