"""Sconti: tolgono dal prezzo progetto (importo in euro o % sul prezzo prima degli sconti), i costi non cambiano.

Valori calcolati a mano. Base: 16 ore di Senior = 2 giorni, ricavi 1.700,00, costi 660,00.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.engine import (
    CalculationError,
    CEInput,
    DiscountInput,
    ExtraCostInput,
    LineInput,
    PhaseInput,
    ProfileRate,
    calculate,
    validate,
)

D = Decimal
RATES = {"Senior": ProfileRate(D("850"), D("330"))}


def ce(discounts=(), extras=(), contingency="0", **kw):
    return CEInput(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 3, 31),
        mode="hours",
        phases=[
            PhaseInput("Fase", [LineInput("Attività", "Senior", hours=D("16"))], D(contingency))
        ],
        rates=RATES,
        extra_costs=list(extras),
        discounts=list(discounts),
        **kw,
    )


def amount(value="200", description="Sconto cliente"):
    return DiscountInput(description, "amount", D(value))


def percent(value="10", description="Sconto volume"):
    return DiscountInput(description, "percent", D(value))


def test_without_discounts_nothing_changes():
    r = calculate(ce())
    assert r.discount_items == []
    assert (r.discounts.revenue, r.discounts.cost, r.discounts.margin) == (D("0.00"),) * 3
    assert r.total.revenue == D("1700.00") and r.total.cost == D("660.00")


def test_an_amount_lowers_the_price_and_leaves_the_costs():
    r = calculate(ce([amount("200")]))
    assert r.discount_items[0].amount == D("200.00") and r.discount_items[0].kind == "amount"
    assert (r.discounts.revenue, r.discounts.cost) == (D("-200.00"), D("0.00"))
    assert r.total.revenue == D("1500.00") and r.total.cost == D("660.00")
    assert r.total.margin == D("840.00")
    assert r.kpis.price_project == D("1500.00")


def test_a_percentage_is_on_the_price_before_the_discounts():
    r = calculate(ce([percent("10")]))
    assert r.discount_items[0].amount == D("170.00")
    assert r.total.revenue == D("1530.00") and r.total.cost == D("660.00")


def test_percentages_are_not_compounded():
    r = calculate(ce([percent("10"), percent("10")]))
    assert [d.amount for d in r.discount_items] == [D("170.00"), D("170.00")]
    assert r.total.revenue == D("1360.00")


def test_the_base_includes_contingency_and_extra_costs():
    r = calculate(
        ce(
            [percent("10"), amount("100")],
            extras=[ExtraCostInput("Viaggi", D("1000"), D("20"))],
            contingency="10",
        )
    )
    # 1.700 + 170 di contingency + 1.200 di costi vari = 3.070 prima degli sconti
    assert r.discount_items[0].amount == D("307.00")
    assert r.discounts.revenue == D("-407.00")
    assert r.total.revenue == D("2663.00") and r.total.cost == D("1660.00")


def test_each_row_is_rounded_to_the_cent_and_summed():
    r = calculate(ce([percent("0.33")] * 3))  # 1.700 x 0,33% = 5,61 per riga
    assert [d.amount for d in r.discount_items] == [D("5.61")] * 3
    assert r.discounts.revenue == D("-16.83")


def test_the_max_discount_and_fee_start_from_the_discounted_price():
    r = calculate(ce([amount("200")], max_discount_pct=D("10")))
    assert r.kpis.price_min == D("1350.00")  # 1.500 x 0,9
    assert r.kpis.fee_media_min == D("675.00")  # 1.350 / 2 giornate


def test_the_signed_price_margin_is_unaffected_by_the_rows():
    r = calculate(ce([amount("200")], signed_price=D("1400")))
    assert r.kpis.margin_signed == D("740.00")  # 1.400 - 660


def test_discounts_do_not_touch_days_hours_or_monthly_staffing():
    base, disc = calculate(ce()), calculate(ce([amount("200")]))
    assert disc.total.days == base.total.days
    assert [m.revenue for m in disc.monthly] == [m.revenue for m in base.monthly]


def test_the_discount_can_zero_the_price_but_not_exceed_it():
    assert calculate(ce([amount("1700")])).total.revenue == D("0.00")
    with pytest.raises(CalculationError, match="supera il prezzo"):
        calculate(ce([amount("1700.01")]))
    with pytest.raises(CalculationError, match="supera il prezzo"):
        calculate(ce([percent("60"), percent("50")]))


@pytest.mark.parametrize(
    ("kind", "value", "fragment"),
    [
        ("amount", "-1", "l'importo"),
        ("amount", "10.001", "l'importo"),
        ("amount", "10000000000", "l'importo"),
        ("percent", "-0.01", "la percentuale"),
        ("percent", "100.01", "la percentuale"),
        ("percent", "10.123", "la percentuale"),
        ("fixed", "10", "il tipo"),
    ],
)
def test_invalid_rows_are_reported_with_their_row(kind, value, fragment):
    issues = validate(ce([amount("5"), DiscountInput("Cattivo", kind, D(value))]))
    assert len(issues) == 1
    assert "Sconti, riga 2 ('Cattivo')" in issues[0] and fragment in issues[0]


def test_limits_and_row_count():
    assert validate(ce([percent("0"), percent("100"), amount("0"), amount("9999999999.99")])) == []
    assert validate(ce([amount("1")] * 100)) == []
    assert "al massimo 100 righe" in validate(ce([amount("1")] * 101))[0]
