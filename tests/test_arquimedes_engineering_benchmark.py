"""Arquimedes Engineering Benchmark / CPM: reference constraints independent of engine.

All activities and networks are fictitious. No database access or writes.
The reference below enumerates feasible integer-day schedules; it does not
reuse the CPM topological pass or the engine's slack formulas.
"""
from __future__ import annotations

from itertools import product

import pytest

from models import cpm


def independent_reference(durations, edges):
    names = tuple(durations)
    solutions = []
    horizon = sum(durations.values()) + sum(abs(e[3]) for e in edges) + 2
    for times in product(range(horizon + 1), repeat=len(names)):
        starts = dict(zip(names, times))
        finishes = {n: starts[n] + durations[n] for n in names}
        ok = True
        for p, s, kind, lag in edges:
            earlier = finishes[p] if kind[0] == "T" else starts[p]
            later = finishes[s] if kind[1] == "T" else starts[s]
            if later < earlier + lag:
                ok = False
                break
        if ok:
            solutions.append((starts, finishes, max(finishes.values())))
    assert solutions, "independent reference: no feasible schedule"
    deadline = min(result[2] for result in solutions)
    optimal = [result for result in solutions if result[2] <= deadline]
    early = {n: min(x[0][n] for x in optimal) for n in names}
    late = {n: max(x[0][n] for x in optimal) for n in names}
    # Hold other activities' early starts fixed and delay only the tested
    # activity, without violating any constraint nor the project finish.
    free = {}
    for n in names:
        feasible = []
        for t in range(early[n], horizon + 1):
            trial = dict(early, **{n: t})
            finish = {k: trial[k] + durations[k] for k in names}
            if max(finish.values()) > deadline:
                continue
            if all(
                (finish[s] if kind[1] == "T" else trial[s]) >=
                (finish[p] if kind[0] == "T" else trial[p]) + lag
                for p, s, kind, lag in edges
            ):
                feasible.append(t - early[n])
        free[n] = max(feasible)
    return deadline, early, late, free


@pytest.mark.parametrize("durations,edges", [
    ({"A": 2, "B": 4, "C": 3, "D": 2},
     [("A", "B", "TI", 0), ("A", "C", "TI", 0),
      ("B", "D", "TI", 0), ("C", "D", "TI", 0)]),
    ({"A": 5, "B": 3}, [("A", "B", "II", 10)]),
    ({"A": 5, "B": 2}, [("A", "B", "TT", 2)]),
    ({"A": 3, "B": 2}, [("A", "B", "IT", 6)]),
    ({"A": 5, "B": 3}, [("A", "B", "TI", -2)]),
    ({"A": 2, "B": 2, "C": 2},
     [("A", "B", "TI", 0), ("A", "C", "TI", 0)]),
])
def test_cpm_against_independent_enumerator(monkeypatch, durations, edges):
    saved = []
    monkeypatch.setattr(cpm, "listar_atividades", lambda project_id: [
        {"id": n, "nome": n, "duracao_dias": d} for n, d in durations.items()
    ])
    monkeypatch.setattr(cpm, "listar_dependencias", lambda project_id: [
        {"predecessora_id": p, "sucessora_id": s,
         "tipo": kind, "lag_dias": lag} for p, s, kind, lag in edges
    ])
    monkeypatch.setattr(cpm, "salvar_resultado_cpm",
                        lambda ident, result: saved.append((ident, result)))
    deadline, early, late, free = independent_reference(durations, edges)
    output = cpm.calcular_caminho_critico("FICTICIO-CPM")
    assert output["duracao_total_dias"] == pytest.approx(deadline, abs=1e-6)
    by_id = {a["id"]: a for a in output["atividades"]}
    for ident in durations:
        got = by_id[ident]
        assert got["es"] == pytest.approx(early[ident], abs=1e-6)
        assert got["ls"] == pytest.approx(late[ident], abs=1e-6)
        assert got["ef"] == pytest.approx(early[ident] + durations[ident], abs=1e-6)
        assert got["lf"] == pytest.approx(late[ident] + durations[ident], abs=1e-6)
        assert got["folga_total"] == pytest.approx(late[ident]-early[ident], abs=1e-6)
        assert got["folga_livre"] == pytest.approx(free[ident], abs=1e-6)
        assert got["critica"] == (late[ident] == early[ident])
    assert len(saved) == len(durations)


def test_invalid_orphan_edge_never_persists(monkeypatch):
    saved = []
    monkeypatch.setattr(cpm, "listar_atividades", lambda project_id: [
        {"id": "A", "nome": "A", "duracao_dias": 2}
    ])
    monkeypatch.setattr(cpm, "listar_dependencias", lambda project_id: [
        {"predecessora_id": "A", "sucessora_id": "NONEXISTENT",
         "tipo": "TI", "lag_dias": 0}
    ])
    monkeypatch.setattr(cpm, "salvar_resultado_cpm",
                        lambda *a, **kw: saved.append((a, kw)))
    with pytest.raises(cpm.RedeInvalidaError, match="invalida"):
        cpm.calcular_caminho_critico("FICTICIO-CPM")
    assert saved == []


def test_invalid_duration_never_persists(monkeypatch):
    saved = []
    monkeypatch.setattr(cpm, "listar_atividades", lambda pid: [
        {"id": "A", "nome": "A", "duracao_dias": float("nan")}
    ])
    monkeypatch.setattr(cpm, "listar_dependencias", lambda pid: [])
    monkeypatch.setattr(cpm, "salvar_resultado_cpm",
                        lambda *a, **k: saved.append(a))
    with pytest.raises(cpm.RedeInvalidaError, match="finitas"):
        cpm.calcular_caminho_critico("FICTICIO-CPM")
    assert saved == []
