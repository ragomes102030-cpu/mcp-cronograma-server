"""Independent civil calendar references for stateless CPM.

No production database, no timezone inference, exclusive interval boundaries.
"""
import pytest
from public_mcp import calcular_cpm_com_calendario, calcular_cpm_com_evidencia


def _run(durations=(2, 1), calendar=None, start="2026-11-02"):
    return calcular_cpm_com_calendario(
        [{"id":"A","duracao_dias":durations[0]},
         {"id":"B","duracao_dias":durations[1]}],
        [{"predecessora_id":"A","sucessora_id":"B","tipo":"TI","lag_dias":0}],
        start, calendar or {"modo":"uteis","calendar_id":"TESTE",
                            "dias_semana":[0,1,2,3,4], "feriados":["2026-11-03"]}
    )


def test_weekend_and_holiday_exact_reference():
    r=_run()
    by={a["id"]:a for a in r["atividades"]}
    assert (by["A"]["data_inicio"],by["A"]["data_ultimo_dia_trabalhado"],
            by["A"]["data_fim_exclusiva"]) == (
            "2026-11-02","2026-11-04","2026-11-05")
    assert (by["B"]["data_inicio"],by["B"]["data_ultimo_dia_trabalhado"],
            by["B"]["data_fim_exclusiva"]) == (
            "2026-11-05","2026-11-05","2026-11-06")
    assert r["duracao_projeto_dias"] == 3
    assert r["data_fim_projeto_exclusiva"] == "2026-11-06"
    assert r["calendar_id"] == "TESTE"
    assert r["persistido"] is False


def test_friday_finishes_exclusive_monday():
    r=calcular_cpm_com_calendario([{"id":"A","duracao_dias":1}], [],
        "2026-11-06", {"modo":"uteis"})
    assert r["atividades"][0]["data_fim_exclusiva"] == "2026-11-09"
    assert r["atividades"][0]["data_ultimo_dia_trabalhado"] == "2026-11-06"


def test_non_working_start_rolls_to_first_workday():
    r=calcular_cpm_com_calendario([{"id":"A","duracao_dias":1}], [],
        "2026-11-07", {"modo":"uteis"})
    assert r["data_inicio_projeto"] == "2026-11-09"
    assert r["data_fim_projeto_exclusiva"] == "2026-11-10"


def test_workday_constraints_ii_tt_it_and_negative_lag():
    base=[{"id":"A","duracao_dias":5},{"id":"B","duracao_dias":3}]
    for kind,lag in [("TI",-2),("II",2),("TT",1),("IT",7)]:
        edges=[{"predecessora_id":"A","sucessora_id":"B","tipo":kind,"lag_dias":lag}]
        raw=calcular_cpm_com_evidencia(base,edges)
        dated=calcular_cpm_com_calendario(base,edges,"2026-11-02",{"modo":"uteis"})
        assert dated["duracao_projeto_dias"] == raw["duracao_projeto_dias"]
        assert [(x["ES"],x["EF"],x["LS"],x["LF"]) for x in dated["atividades"]] == [
            (x["ES"],x["EF"],x["LS"],x["LF"]) for x in raw["atividades"]]


def test_corridos_preserves_half_day_clock():
    r=calcular_cpm_com_calendario([{"id":"A","duracao_dias":0.5}], [],
        "2026-11-02", {"modo":"corridos"})
    a=r["atividades"][0]
    assert a["data_hora_inicio"] == "2026-11-02T00:00:00"
    assert a["data_hora_fim_exclusiva"] == "2026-11-02T12:00:00"


@pytest.mark.parametrize("bad_calendar", [
    {"modo":"uteis","dias_semana":[7]},
    {"modo":"uteis","dias_semana":[]},
    {"modo":"uteis","feriados":["30-10-2026"]},
    {"modo":"uteis","dias_semana":[1,1]},
    {"modo":"inexistente"},
    {"modo":"corridos","feriados":["2026-11-03"]},
])
def test_bad_calendar_rejected(bad_calendar):
    with pytest.raises(ValueError):
        _run(calendar=bad_calendar)


@pytest.mark.parametrize("duration", [0,1.5,-2,float("nan"),float("inf")])
def test_workday_duration_must_be_integer_positive(duration):
    with pytest.raises(ValueError):
        _run(durations=(duration,2))


def test_fractional_lag_rejected_before_any_rounded_calculation():
    with pytest.raises(ValueError,match="lag_dias"):
        calcular_cpm_com_calendario(
            [{"id":"A","duracao_dias":2},{"id":"B","duracao_dias":2}],
            [{"predecessora_id":"A","sucessora_id":"B","tipo":"TI","lag_dias":0.5}],
            "2026-11-02",{"modo":"uteis"})


def test_invalid_orphan_network_not_returned():
    with pytest.raises(ValueError):
        calcular_cpm_com_calendario([{"id":"A","duracao_dias":2}],
            [{"predecessora_id":"A","sucessora_id":"X"}],"2026-11-02",{"modo":"uteis"})
