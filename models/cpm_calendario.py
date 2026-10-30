"""Map deterministic CPM offsets to explicit civil or working-day calendar dates.

No database, no inference of holidays, no changes to CPM constraints.
Interval convention is [start, finish) with an *exclusive* finish boundary.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from math import isfinite


def _integer(value: object, name: str, *, positive: bool = False) -> int:
    if type(value) not in (int, float) or not isfinite(value):
        raise ValueError(f"{name}: exige inteiro finito")
    if value != int(value) or (positive and value <= 0) or abs(value) > 36500:
        raise ValueError(f"{name}: inteiro fora do dominio")
    return int(value)


def aplicar_calendario_cpm(
    resultado_cpm: dict, atividades_entrada: list[dict], dependencias: list[dict],
    data_inicio: str, calendario: dict,
) -> dict:
    if not isinstance(calendario, dict):
        raise ValueError("calendario deve ser objeto explicito")
    try:
        inicio = date.fromisoformat(data_inicio)
    except (ValueError, TypeError) as exc:
        raise ValueError("data_inicio deve ser ISO YYYY-MM-DD") from exc
    modo = calendario.get("modo")
    if modo not in ("corridos", "uteis"):
        raise ValueError("modo do calendario deve ser corridos ou uteis")
    if not resultado_cpm.get("valid") or resultado_cpm.get("persistido") is not False:
        raise ValueError("CPM invalido ou nao comprovadamente stateless")
    if len(resultado_cpm.get("atividades", [])) != len(atividades_entrada):
        raise ValueError("CPM retornou numero de atividades inconsistente")
    if modo == "uteis":
        for a in atividades_entrada:
            _integer(a.get("duracao_dias"), "duracao_dias", positive=True)
        for d in dependencias:
            _integer(d.get("lag_dias", 0) or 0, "lag_dias")
    dias = calendario.get("dias_semana", [0, 1, 2, 3, 4])
    feriados_raw = calendario.get("feriados", [])
    if modo == "uteis":
        if (not isinstance(dias, list) or not dias or len(dias) > 7
            or any(type(d) is not int or d not in range(7) for d in dias)
            or len(set(dias)) != len(dias)):
            raise ValueError("dias_semana precisa conter dias distintos entre 0 e 6")
        if not isinstance(feriados_raw, list) or len(feriados_raw) > 500:
            raise ValueError("feriados invalidos")
        try:
            feriados = {date.fromisoformat(v) for v in feriados_raw}
        except (ValueError, TypeError) as exc:
            raise ValueError("feriados exigem datas ISO validas") from exc
    else:
        if "dias_semana" in calendario or "feriados" in calendario:
            raise ValueError("calendario corridos nao aceita regras de dias uteis")
        feriados = set()
    limite = max(_integer(resultado_cpm["duracao_projeto_dias"], "prazo CPM", positive=True)
                 if modo == "uteis" else 0, 0)
    if modo == "uteis":
        for a in resultado_cpm["atividades"]:
            for campo in ("ES", "EF", "LS", "LF", "folga_total", "folga_livre"):
                _integer(a[campo], campo)
            limite = max(limite, int(a["LF"]))
        if limite > 36500:
            raise ValueError("prazo maior que limite de 36500 dias uteis")
        # The index i points to the start of the i-th *available* working
        # day. The completion of N workdays maps to index N (exclusive).
        # Prevent infinitely scanning calendars made entirely of holidays.
        cursor = inicio
        offsets = []
        while len(offsets) <= limite:
            if (cursor.weekday() in dias and cursor not in feriados):
                offsets.append(cursor)
            cursor += timedelta(days=1)
            if (cursor - inicio).days > 365000:
                raise ValueError("calendario nao contem dias uteis suficientes")
    else:
        offsets = None

    def instante(dia: float) -> datetime:
        if not isinstance(dia, (float, int)) or not isfinite(dia) or dia < 0 or dia > 36500:
            raise ValueError("offset de calendario invalido")
        return (datetime.combine(offsets[int(dia)], time.min)
                if modo == "uteis" else
                datetime.combine(inicio, time.min) + timedelta(days=dia))

    novas = []
    for row in resultado_cpm["atividades"]:
        es, ef = instante(row["ES"]), instante(row["EF"])
        ls, lf = instante(row["LS"]), instante(row["LF"])
        ultima = (offsets[int(row["EF"]) - 1] if modo == "uteis"
                  else (ef - timedelta(microseconds=1)).date())
        novas.append({
            **row,
            "data_inicio": es.date().isoformat(),
            "data_fim_exclusiva": ef.date().isoformat(),
            "data_ultimo_dia_trabalhado": ultima.isoformat(),
            "data_hora_inicio": es.isoformat(),
            "data_hora_fim_exclusiva": ef.isoformat(),
            "data_inicio_tarde": ls.date().isoformat(),
            "data_fim_tarde_exclusiva": lf.date().isoformat(),
        })
    fim = instante(resultado_cpm["duracao_projeto_dias"])
    return {
        **resultado_cpm,
        "atividades": novas,
        "data_inicio_projeto": instante(0).date().isoformat(),
        "data_fim_projeto_exclusiva": fim.date().isoformat(),
        "schema_version": "1.0",
        "calculation_version": "cpm-calendario-v1",
        "calendar_id": calendario.get("calendar_id"),
        "calendario_modo": modo,
        "convencao_temporal": (
            "dias uteis discretos; duracao/lag inteiros; fim exclusivo; feriados explicitos"
            if modo == "uteis"
            else "dias corridos; fracao de dia preservada; fim exclusivo"),
        "persistido": False,
    }
