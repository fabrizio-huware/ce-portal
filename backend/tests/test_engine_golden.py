"""Il motore deve restituire gli stessi numeri del foglio reale (cache e ricalcolo LibreOffice)."""

from decimal import Decimal

import pytest

from app.engine import CEInput, LineInput, PhaseInput, calculate
from tests.engine_helpers import (
    FIXTURE,
    base_ce,
    base_phases,
    cents,
    d,
    month,
    rates,
    ratio6,
)

EXPECTED = FIXTURE["expected"]


# ================================================================ CE originale
def test_original_ce_totals_match_the_sheet():
    r = calculate(base_ce())
    assert r.total.revenue == cents(EXPECTED["revenue_total"]) == Decimal("47162.50")
    assert r.total.cost == cents(EXPECTED["cost_total"]) == Decimal("20200.00")
    assert r.total.margin == cents(EXPECTED["margin_total"]) == Decimal("26962.50")
    assert r.total.days == Decimal("58.5000")
    assert r.kpis.weeks == Decimal("11.7000")


def test_original_ce_percentages_match_the_dashboard():
    r = calculate(base_ce())
    dash = EXPECTED["dashboard"]
    assert r.total.margin_pct == ratio6(dash["margin_pct"])  # 57,17%
    assert r.total.cost_ratio == ratio6(dash["cr"])  # 42,83%
    assert r.total.margin_pct + r.total.cost_ratio == Decimal("1.000000")


def test_original_ce_dashboard_kpis():
    k = calculate(base_ce()).kpis
    dash = EXPECTED["dashboard"]
    assert k.price_project == cents(dash["price"])
    assert k.price_min == cents(dash["price_min"])  # nessuno sconto
    assert k.days_total == d(dash["days_total"]).quantize(Decimal("0.0001"))
    assert k.days_delivery == d(dash["days_tech"]).quantize(Decimal("0.0001"))  # 48,5
    assert k.days_project_management == d(dash["days_pm"]).quantize(Decimal("0.0001"))  # 10
    assert k.fee_media_min == cents(dash["fee_media_min"]) == Decimal("806.20")
    assert k.signed_price is None and k.margin_signed is None and k.fee_media_signed is None


def test_original_ce_breakdown_by_profile_matches_the_sheet():
    r = calculate(base_ce())
    by_name = {p.profile: p for p in r.profiles}
    for name in ("Manager", "Practice", "Senior", "Specialist"):
        assert by_name[name].hours == d(EXPECTED["hours_by_profile"][name]).quantize(
            Decimal("0.0001")
        ), name
        assert by_name[name].revenue == cents(EXPECTED["revenue_by_profile"][name]), name
        assert by_name[name].cost == cents(EXPECTED["cost_by_profile"][name]), name
        assert by_name[name].hours_share == ratio6(EXPECTED["share_by_profile"][name]), name
    assert set(by_name) == {"Manager", "Practice", "Senior", "Specialist"}  # solo i profili usati
    assert sum(p.hours_share for p in r.profiles) == Decimal("1.000000")


def test_original_ce_has_no_external_services_and_no_contingency():
    r = calculate(base_ce())
    assert r.external.revenue == r.external.cost == Decimal("0.00")
    assert r.external.margin_pct is None  # nessuna divisione per zero
    assert r.contingency.revenue == Decimal("0.00")
    assert r.internal.revenue == r.total.revenue
    assert r.warnings == []


def test_original_ce_monthly_staffing_adds_up_to_the_totals():
    r = calculate(base_ce())
    assert [m.work_days for m in r.months] == [
        17,
        20,
        22,
        22,
    ]  # gen: 22 feriali - 5 inseriti a mano
    # giornate e ore sono esatte
    assert sum(m.days for m in r.monthly) == r.total.days
    assert sum(m.hours for m in r.monthly) == Decimal("468.0000")
    assert sum(line.hours for line in r.lines) == Decimal("468.0000")
    # gli importi sono arrotondati al centesimo voce per voce: la somma delle voci può
    # scostarsi dal totale (calcolato sul valore esatto, come nel foglio) di 1 centesimo a voce
    tolerance = Decimal("0.01") * len(r.monthly)
    assert abs(sum(m.revenue for m in r.monthly) - r.total.revenue) <= tolerance
    assert abs(sum(m.cost for m in r.monthly) - r.total.cost) <= tolerance


def test_original_ce_per_phase_hours():
    r = calculate(base_ce())
    hours = {p.name: p.hours for p in r.phases}
    assert hours["PM"] == Decimal("80.0000")  # 10 giornate di project management
    assert hours["AN"] == Decimal("116.0000")
    assert hours["TA"] == Decimal("216.0000")
    assert sum(hours.values()) == Decimal("468.0000")


# ================================================================ scenario A
# contingency 10% su tutte le fasi, max sconto 10%, prezzo firmato 40.000
@pytest.fixture(scope="module")
def scenario_a():
    sc = FIXTURE["scenarios"]["A"]
    ce = base_ce(
        phases=base_phases({c["code"]: sc["contingency_pct_all"] for c in FIXTURE["phases"]}),
        max_discount_pct=d(sc["max_discount_pct"]),
        signed_price=d(sc["signed_price"]),
    )
    return calculate(ce), sc["sheet"]


def test_scenario_a_contingency_matches_the_sheet(scenario_a):
    r, sheet = scenario_a
    assert r.contingency.revenue == cents(sheet["E9"]) == Decimal("4716.25")
    assert r.contingency.cost == Decimal("0.00")  # la contingency non ha costi
    assert r.kpis.days_total_with_contingency == d(sheet["M8"]).quantize(Decimal("0.0001"))  # 64,35
    assert r.kpis.weeks_with_contingency == d(sheet["M9"]).quantize(Decimal("0.0001"))  # 12,87


def test_scenario_a_price_and_discount_match_the_sheet(scenario_a):
    r, sheet = scenario_a
    k = r.kpis
    assert k.price_project == cents(sheet["DB_C3"]) == Decimal("51878.75")
    assert k.price_min == cents(sheet["DB_D3"]) == Decimal("46690.88")  # 46.690,875 arrotondato
    assert k.fee_media_min == cents(sheet["DB_E3"]) == Decimal("798.13")
    assert k.fee_media_signed == cents(sheet["DB_E4"]) == Decimal("683.76")
    assert (k.days_total, k.days_project_management) == (Decimal("58.5000"), Decimal("10.0000"))
    assert k.days_delivery == d(sheet["DB_G3"]).quantize(Decimal("0.0001"))
    assert k.days_total_with_contingency != k.days_total  # le giornate "base" restano 58,5


def test_scenario_a_margins_match_the_sheet(scenario_a):
    r, sheet = scenario_a
    assert r.total.revenue == cents(sheet["E16"])
    assert r.total.margin == cents(sheet["F16"]) == Decimal("31678.75")
    assert r.total.margin_pct == ratio6(sheet["DB_F7"])
    assert r.total.cost_ratio == ratio6(sheet["DB_H7"]) == ratio6(sheet["G16"])


def test_scenario_a_signed_price_block_matches_the_sheet(scenario_a):
    k = scenario_a[0].kpis
    sheet = scenario_a[1]
    assert k.margin_signed == cents(sheet["DB_F12"]) == Decimal("19800.00")
    assert k.margin_pct_signed == ratio6(sheet["DB_E12"]) == Decimal("0.495000")
    assert k.cost_ratio_signed == ratio6(sheet["DB_G12"]) == Decimal("0.505000")


# ================================================================ scenario A2
def test_per_phase_contingency_is_exact_and_differs_from_the_sheet_average():
    """Il foglio applica la media pesata sulle ore al ricavo totale; il portale calcola fase per fase.

    PM 20% su 10.375 + SD 5% su 2.550 + TA 10% su 20.200 = 4.222,50.
    Il foglio dà 3.910,05: sottostima di 312,45 perché la fase PM ha ore più costose.
    """
    sc = FIXTURE["scenarios"]["A2"]
    r = calculate(base_ce(phases=base_phases(sc["contingency_pct"])))
    by_phase = {p.name: p.contingency_revenue for p in r.phases}
    assert by_phase["PM"] == Decimal("2075.00")
    assert by_phase["SD"] == Decimal("127.50")
    assert by_phase["TA"] == Decimal("2020.00")
    assert r.contingency.revenue == Decimal("4222.50")
    assert cents(sc["sheet"]["E9"]) == Decimal("3910.05")  # valore del foglio, documentato
    assert r.contingency.revenue - cents(sc["sheet"]["E9"]) == Decimal("312.45")


# ================================================================ scenario B
@pytest.fixture(scope="module")
def scenario_b():
    sc = FIXTURE["scenarios"]["B"]
    months = [month(2026, m) for m in (1, 2, 3, 4)]
    lines = [
        LineInput(
            activity=row["profile"],
            profile=row["profile"],
            allocations={m: d(p) for m, p in zip(months, row["pct"], strict=True)},
        )
        for row in sc["rows"]
    ]
    ce = CEInput(
        start_date=month(2026, 1).replace(day=20),
        end_date=month(2026, 4).replace(day=20),
        mode="percent",
        phases=[PhaseInput("Allocazione", lines)],
        rates=rates(),
        non_working_days={month(2026, 1): 5},
    )
    return calculate(ce), sc["sheet"]


def test_percent_mode_work_days_per_month(scenario_b):
    r, sheet = scenario_b
    assert [m.work_days for m in r.months] == [int(sheet[c]) for c in ("N12", "O12", "P12", "Q12")]
    assert [m.work_days for m in r.months] == [17, 20, 22, 22]


def test_percent_mode_monthly_staffing_matches_the_sheet(scenario_b):
    r, sheet = scenario_b
    for m, col in zip(r.monthly, "NOPQ", strict=True):
        assert m.fte == ratio6(sheet[f"{col}3"]), col  # FTE del mese
        assert m.days == d(sheet[f"{col}4"]).quantize(Decimal("0.0001")), col  # man-days
        assert m.revenue == cents(sheet[f"{col}5"]), col  # "EXT. COST" del foglio = ricavi
        assert m.cost == cents(sheet[f"{col}6"]), col  # "INT. COST"
    assert sum(m.fte for m in r.monthly) == d(sheet["AB3"])  # 7,4


def test_percent_mode_totals_match_the_sheet(scenario_b):
    r, sheet = scenario_b
    assert r.total.days == d(sheet["AB4"]).quantize(Decimal("0.0001")) == Decimal("148.8500")
    assert r.total.revenue == cents(sheet["AB5"]) == Decimal("125762.50")
    assert r.total.cost == cents(sheet["AB6"]) == Decimal("56714.00")
    assert r.total.margin == cents(sheet["G3"]) == Decimal("69048.50")


def test_percent_mode_per_line_matches_the_sheet(scenario_b):
    r, sheet = scenario_b
    for line, row in zip(r.lines, (15, 16, 17, 18), strict=True):
        assert line.days == d(sheet[f"AB{row}"]).quantize(Decimal("0.0001")), line.profile
        assert line.revenue == cents(sheet[f"AC{row}"]), line.profile
        assert line.cost == cents(sheet[f"AD{row}"]), line.profile


def test_percent_mode_line_fte_is_the_work_day_weighted_average(scenario_b):
    """Colonna FTE del foglio (non ricalcolabile da LibreOffice): verificata a mano."""
    r, _ = scenario_b
    fte = {line.profile: line.fte for line in r.lines}
    assert fte["Manager"] == Decimal("0.250000")  # 25% ogni mese
    assert fte["Practice"] == Decimal("0.100000")
    assert fte["Senior"] == Decimal("0.592593")  # 48 giorni / 81 lavorativi
    assert fte["Specialist"] == Decimal("0.895062")  # 72,5 / 81
