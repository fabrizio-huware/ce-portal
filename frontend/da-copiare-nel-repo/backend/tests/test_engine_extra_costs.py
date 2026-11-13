"""Costi vari: una riga è un costo con un ricarico sul costo, senza giornate né mesi.

Valori calcolati a mano. Base: 16 ore di Senior = 2 giorni, ricavi 1.700,00, costi 660,00.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.engine import (
    CalculationError,
    CEInput,
    ExtraCostInput,
    LineInput,
    PhaseInput,
    ProfileRate,
    calculate,
    validate,
)

D = Decimal
RATES = {"Senior": ProfileRate(D("850"), D("330"))}


def ce(extras=(), contingency="0", with_work=True, **kw):
    lines = [LineInput("Attività", "Senior", hours=D("16"))] if with_work else []
    return CEInput(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 3, 31),
        mode="hours",
        phases=[PhaseInput("Fase", lines, D(contingency))],
        rates=RATES,
        extra_costs=list(extras),
        **kw,
    )


def extra(cost="1000", markup="20", description="Viaggi"):
    return ExtraCostInput(description, D(cost), D(markup))


def test_without_extra_costs_nothing_changes():
    r = calculate(ce())
    assert r.extra_costs == []
    assert (r.extras.revenue, r.extras.cost, r.extras.margin) == (D("0.00"),) * 3
    assert r.total.revenue == D("1700.00") and r.total.cost == D("660.00")


def test_a_line_is_cost_times_one_plus_markup():
    r = calculate(ce([extra("1000", "20")]))
    row = r.extra_costs[0]
    assert (row.cost, row.markup_pct, row.revenue, row.margin) == (
        D("1000.00"),
        D("20"),
        D("1200.00"),
        D("200.00"),
    )
    assert row.description == "Viaggi"


def test_markup_is_on_the_cost_not_on_the_price():
    """Costo 1.000 e ricarico 20%: ricavo 1.200 (non 1.250, che sarebbe un margine del 20%)."""
    assert calculate(ce([extra("1000", "20")])).extra_costs[0].revenue == D("1200.00")


def test_zero_markup_passes_the_cost_through_with_no_margin():
    r = calculate(ce([extra("500", "0")]))
    assert r.extra_costs[0].revenue == D("500.00") and r.extra_costs[0].margin == D("0.00")


def test_extras_add_to_revenue_cost_and_margin_of_the_total():
    r = calculate(ce([extra("1000", "20"), extra("200", "50", "Licenze")]))
    # ricavi extra 1.200 + 300 = 1.500; costi extra 1.200
    assert (r.extras.revenue, r.extras.cost, r.extras.margin) == (
        D("1500.00"),
        D("1200.00"),
        D("300.00"),
    )
    assert r.total.revenue == D("3200.00")  # 1.700 + 1.500
    assert r.total.cost == D("1860.00")  # 660 + 1.200
    assert r.total.margin == D("1340.00")
    assert r.total.margin_pct == D("0.418750")  # 1.340 / 3.200
    assert r.kpis.price_project == D("3200.00")


def test_each_line_is_rounded_to_the_cent_and_the_lines_add_up_to_the_total():
    # 333,33 x 1,155 = 384,99615 -> 385,00;  100,01 x 1,005 = 100,51005 -> 100,51
    r = calculate(ce([extra("333.33", "15.5"), extra("100.01", "0.5", "Altro")]))
    assert [e.revenue for e in r.extra_costs] == [D("385.00"), D("100.51")]
    assert r.extras.revenue == D("485.51") == sum(e.revenue for e in r.extra_costs)
    assert r.extra_costs[0].margin == D("51.67")  # 385,00 - 333,33


def test_the_total_is_the_sum_of_the_rounded_rows_not_a_separately_rounded_sum():
    """10,01 x 1,0004 = 10,014004 -> 10,01 per riga; tre righe: 30,03 (la somma esatta darebbe 30,04)."""
    r = calculate(ce([extra("10.01", "0.04", f"Riga {i}") for i in range(3)]))
    assert [e.revenue for e in r.extra_costs] == [D("10.01")] * 3
    assert r.extras.revenue == D("30.03") and r.total.revenue == D("1730.03")


def test_contingency_does_not_apply_to_extra_costs():
    r = calculate(ce([extra("1000", "20")], contingency="10"))
    assert r.contingency.revenue == D("170.00")  # solo il 10% dei servizi (1.700)
    assert r.extras.revenue == D("1200.00")
    assert r.total.revenue == D("3070.00")  # 1.700 + 170 + 1.200


def test_extras_have_no_days_hours_fte_or_months():
    base, with_extras = calculate(ce()), calculate(ce([extra()]))
    assert with_extras.total.days == base.total.days == D("2")
    assert with_extras.extras.days == D("0")
    assert with_extras.kpis.days_total == base.kpis.days_total
    assert with_extras.kpis.days_total_with_contingency == base.kpis.days_total_with_contingency
    assert with_extras.kpis.days_project_management == base.kpis.days_project_management
    assert [m.revenue for m in with_extras.monthly] == [m.revenue for m in base.monthly]
    assert with_extras.lines == base.lines and with_extras.profiles == base.profiles


def test_max_discount_applies_to_the_whole_price_extras_included():
    r = calculate(ce([extra("1000", "20")], max_discount_pct=D("10")))
    assert r.kpis.price_min == D("2610.00")  # (1.700 + 1.200) x 0,90


def test_average_fee_only_looks_at_services():
    """Senza giornate i costi vari non devono gonfiare la fee media."""
    r = calculate(ce([extra("1000", "20")], max_discount_pct=D("10"), signed_price=D("3000")))
    assert r.kpis.fee_media_min == D("765.00")  # (1.700 x 0,90) / 2 giorni
    assert r.kpis.fee_media_signed == D("900.00")  # (3.000 - 1.200) / 2 giorni
    assert r.kpis.fee_media_min == calculate(ce(max_discount_pct=D("10"))).kpis.fee_media_min


def test_signed_margin_counts_the_cost_of_the_extras():
    r = calculate(ce([extra("1000", "20")], signed_price=D("3000")))
    assert r.kpis.margin_signed == D("1340.00")  # 3.000 - (660 + 1.000)
    assert r.kpis.cost_ratio_signed == D("0.553333")  # 1.660 / 3.000


def test_a_ce_with_only_extra_costs_is_calculated():
    r = calculate(ce([extra("1000", "20")], with_work=False))
    assert r.total.days == D("0") and r.total.revenue == D("1200.00")
    assert r.kpis.fee_media_min is None  # nessuna giornata: niente divisione per zero


@pytest.mark.parametrize(
    ("cost", "markup", "fragment"),
    [
        ("-1", "0", "il costo"),
        ("10.001", "0", "il costo"),
        ("10000000000", "0", "il costo"),
        ("10", "-100.01", "il ricarico"),
        ("10", "-1000", "il ricarico"),
        ("10", "1000.01", "il ricarico"),
        ("10", "10.123", "il ricarico"),
    ],
)
def test_invalid_extra_costs_are_reported_with_their_row(cost, markup, fragment):
    issues = validate(ce([extra("5", "0"), extra(cost, markup, "Cattiva")]))
    assert len(issues) == 1
    assert "Costi vari, riga 2 ('Cattiva')" in issues[0] and fragment in issues[0]
    with pytest.raises(CalculationError):
        calculate(ce([extra(cost, markup)]))


def test_at_most_one_hundred_rows():
    assert validate(ce([extra()] * 100)) == []
    assert "al massimo 100 righe" in validate(ce([extra()] * 101))[0]


def test_limits_are_accepted():
    assert validate(ce([extra("0", "0"), extra("9999999999.99", "1000")])) == []


# ------------------------------------------------------------------ ricarico negativo
def test_a_negative_markup_gives_a_revenue_below_the_cost():
    r = calculate(ce([extra("1000", "-25")]))
    line = r.extra_costs[0]
    assert (line.revenue, line.margin) == (D("750.00"), D("-250.00"))
    assert (r.extras.revenue, r.extras.cost, r.extras.margin) == (
        D("750.00"),
        D("1000"),
        D("-250.00"),
    )
    assert r.total.revenue == D("2450.00") and r.total.cost == D("1660.00")


def test_minus_one_hundred_percent_zeroes_the_row_and_the_cost_stays():
    r = calculate(ce([extra("1000", "-100")]))
    assert r.extra_costs[0].revenue == D("0.00") and r.extra_costs[0].margin == D("-1000.00")
    assert r.total.revenue == D("1700.00") and r.total.cost == D("1660.00")


def test_a_negative_row_is_rounded_per_row_and_summed_rounded():
    r = calculate(ce([extra("10.01", "-0.04")] * 3))  # 10,00996 -> 10,01 per riga
    assert [x.revenue for x in r.extra_costs] == [D("10.01")] * 3
    assert r.extras.revenue == D("30.03")


def test_the_whole_ce_can_have_a_negative_margin_because_of_the_extras():
    r = calculate(ce([extra("5000", "-50")]))
    assert r.total.revenue == D("4200.00") and r.total.cost == D("5660.00")
    assert r.total.margin == D("-1460.00") and r.total.margin_pct < 0
    assert r.kpis.fee_media_min is not None  # solo sui servizi: non cambia
