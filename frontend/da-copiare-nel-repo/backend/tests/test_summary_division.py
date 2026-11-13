"""PDF riepilogativo: i ricavi in euro per business unit, senza costi né margini."""

from decimal import Decimal

from app.exports.common import fmt_num
from app.schemas.ce import CEDetail
from app.services.unit_division import NO_EMPLOYEE, business_unit_revenue
from tests.ce_helpers import create
from tests.factories import make_business_unit
from tests.test_ce_business_units import _employee_in
from tests.test_division_and_project import URL, _ce_with, _division_scene, _text

FORBIDDEN_WORDS = ("Contingency", "Costi", "Margine", "Divisione per business unit")


def _detail(api, env, ce) -> CEDetail:
    return CEDetail.model_validate(api.get(f"{URL}/{ce}", headers=env.h(env.admin)).json())


def _summary(api, env, ce, user=None):
    resp = api.get(
        f"{URL}/{ce}/export?format=pdf&variant=summary", headers=env.h(user or env.presale)
    )
    assert resp.status_code == 200
    return _text(resp.content)


def test_the_summary_pdf_has_the_revenue_by_business_unit_and_nothing_else(api, env, session):
    ce, *_ = _division_scene(api, env, session)
    detail = _detail(api, env, ce)
    text = _summary(api, env, ce)
    assert "Ricavi per business unit" in text and "% dei ricavi" in text
    for label in ("Business unit di prova", "Cloud", NO_EMPLOYEE, "practice attuale"):
        assert label in text, label
    for row in business_unit_revenue(session, detail):
        assert fmt_num(row.revenue) in text, row.label  # l'importo in euro di ogni riga
    for word in FORBIDDEN_WORDS:
        assert word not in text, word  # niente costi, margini, contingency a parte
    total = detail.calculation.total
    assert (
        fmt_num(total.cost) not in text and fmt_num(total.margin) not in text
    )  # nemmeno come numeri


def test_the_rows_add_up_to_the_total_and_the_contingency_is_spread_not_shown(api, env, session):
    ce, *_ = _division_scene(api, env, session)  # contingency 10%
    detail = _detail(api, env, ce)
    rows = business_unit_revenue(session, detail)
    labels = [r.label for r in rows]
    assert labels == ["Business unit di prova", "Cloud", NO_EMPLOYEE] or labels[-1] == NO_EMPLOYEE
    assert "Contingency" not in labels
    cal = detail.calculation
    assert sum(r.revenue for r in rows) == cal.total.revenue  # a centesimo
    assert abs(sum(r.share for r in rows) - 1) < Decimal("1e-9")
    lines_only = sum((line.revenue for line in cal.lines), Decimal(0))
    assert (
        cal.contingency.revenue > 0
        and sum(r.revenue for r in rows) - lines_only == cal.contingency.revenue
    )
    by_label = {r.label: r for r in rows}
    assert by_label["Cloud"].revenue > cal.lines[1].revenue  # la sua quota di contingency è dentro


def test_a_rounding_rest_never_breaks_the_total(api, env, session):
    b = make_business_unit(session, name="Cloud")
    ada, bruno = _employee_in(session, env, env.unit, "Ada"), _employee_in(session, env, b, "Bruno")
    session.commit()
    ce = _ce_with(
        api, env, env.presale, "PS-SUM-1-PJT", "Resti", [ada, bruno, ada], extra_lines=True,
        contingency="3.33", units=[str(env.unit.id), str(b.id)],
    )  # fmt: skip
    detail = _detail(api, env, ce)
    rows = business_unit_revenue(session, detail)
    assert sum(r.revenue for r in rows) == detail.calculation.total.revenue
    assert all(r.revenue == r.revenue.quantize(Decimal("0.01")) for r in rows)  # solo centesimi


def test_a_ce_without_lines_has_no_such_section(api, env, session):
    created = create(api, env, env.presale, "PS-SUM-2-PJT")
    text = _summary(api, env, created["ce"]["id"])
    assert "Ricavi per business unit" not in text and "Ricavi per fase" in text


def test_the_viewer_summary_of_an_approved_ce_has_it_too(api, env, session):
    ce, *_ = _division_scene(api, env, session)
    assert api.post(f"{URL}/{ce}/approve", headers=env.h(env.admin)).status_code == 200
    resp = api.get(f"{URL}/summaries/{ce}/export?format=pdf", headers=env.h(env.viewer))
    assert resp.status_code == 200
    text = _text(resp.content)
    assert "Ricavi per business unit" in text and "Cloud" in text
    for word in FORBIDDEN_WORDS:
        assert word not in text, word
    total = _detail(api, env, ce).calculation.total
    assert fmt_num(total.cost) not in text and fmt_num(total.margin) not in text


def test_excel_and_csv_summaries_do_not_change(api, env, session):
    ce, *_ = _division_scene(api, env, session)
    csv = api.get(f"{URL}/{ce}/export?format=csv&variant=summary", headers=env.h(env.presale))
    assert csv.status_code == 200 and "Cloud" not in csv.text  # le business unit sono solo nel PDF
    xlsx = api.get(f"{URL}/{ce}/export?format=xlsx&variant=summary", headers=env.h(env.presale))
    assert xlsx.status_code == 200 and b"Cloud" not in xlsx.content


def test_spread_always_adds_up_and_puts_the_rest_on_the_biggest():
    from app.services.unit_division import spread

    even = spread(Decimal("1.00"), {"a": Decimal(10), "b": Decimal(10), "c": Decimal(10)})
    assert sum(even.values()) == Decimal("1.00")  # 0,33 + 0,33 + 0,33 + il resto
    assert sorted(even.values()) == [Decimal("0.33"), Decimal("0.33"), Decimal("0.34")]
    tiny = spread(Decimal("0.01"), {"a": Decimal(1), "b": Decimal(1)})
    assert sum(tiny.values()) == Decimal("0.01") and sorted(tiny.values()) == [
        Decimal("0.00"),
        Decimal("0.01"),
    ]
    biggest = spread(Decimal("0.10"), {"a": Decimal(1), "b": Decimal(1), "c": Decimal(2)})
    assert biggest == {
        "a": Decimal("0.02"),
        "b": Decimal("0.02"),
        "c": Decimal("0.06"),
    }  # il resto va a «c»
    skewed = spread(Decimal("100.00"), {"a": Decimal(1), "b": Decimal(3)})
    assert skewed == {"a": Decimal("25.00"), "b": Decimal("75.00")}
    assert spread(Decimal("7.00"), {"solo": Decimal(5)}) == {"solo": Decimal("7.00")}
    for amount in (Decimal("0.02"), Decimal("12.34"), Decimal("999.99")):
        weights = {"x": Decimal("3"), "y": Decimal("7"), "z": Decimal("11")}
        assert sum(spread(amount, weights).values()) == amount
