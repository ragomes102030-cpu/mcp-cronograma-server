"""Calendário de dias úteis — converte ES/EF (em "dias de duração" a partir
de um marco zero) em datas de calendário reais.

v1: segunda a sexta são dias úteis; sábado/domingo não. Feriados são uma
lista de datas ISO passada explicitamente por chamada (não persistida em
banco ainda — TODO v2: tabela de feriados por região/projeto).
"""

from __future__ import annotations

from datetime import date, timedelta


def _e_dia_util(d: date, feriados: set[date]) -> bool:
    return d.weekday() < 5 and d not in feriados  # 0=segunda ... 4=sexta


def somar_dias_uteis(inicio: date, dias_uteis: float, feriados: set[date] | None = None) -> date:
    """Anda ``dias_uteis`` dias úteis a partir de ``inicio`` (inclusive).

    Trata fração de dia (ex.: 2.5 dias úteis) avançando o inteiro e
    deixando a fração residual sem efeito prático na data (dias inteiros
    são a granularidade de calendário — a fração fica só no cálculo CPM).
    """
    feriados = feriados or set()
    dias_inteiros = int(dias_uteis)
    atual = inicio
    contados = 0
    if dias_inteiros == 0:
        return inicio
    # Garante que a data de início conte como dia 1 se já for útil.
    while contados < dias_inteiros:
        if _e_dia_util(atual, feriados):
            contados += 1
            if contados == dias_inteiros:
                break
        atual += timedelta(days=1)
    return atual


def gerar_datas(
    data_marco_zero: date,
    es: float,
    ef: float,
    feriados: set[date] | None = None,
) -> tuple[date, date]:
    """Converte ES/EF (dias de duração desde o marco zero) em datas reais."""
    inicio = somar_dias_uteis(data_marco_zero, es, feriados)
    fim = somar_dias_uteis(data_marco_zero, ef, feriados)
    return inicio, fim
