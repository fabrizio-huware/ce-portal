"""Vista ridotta di un CE (la stessa che vede il viewer), ricavata dal dettaglio completo."""

from app.schemas.ce import CEDetail, ViewerCE, ViewerPhase


def reduced_from_detail(detail: CEDetail) -> ViewerCE:
    """Solo giornate di management e delivery, ricavi per fase (contingency inclusa) e totale.

    I costi vari compaiono come un'unica voce "Costi vari" con il solo ricavo: mai descrizioni,
    costi o ricarichi.
    """
    calc = detail.calculation
    phases = [ViewerPhase(name=p.name, revenue=p.revenue_with_contingency) for p in calc.phases]
    if detail.extra_costs:
        phases.append(ViewerPhase(name="Costi vari", revenue=calc.extras.revenue))
    return ViewerCE(
        ce_id=detail.ce.id,
        code=detail.ce.code,
        client_name=detail.header.client.name,
        project_name=detail.header.project_name,
        start_date=detail.header.start_date,
        end_date=detail.header.end_date,
        version_number=detail.version.number,
        approved_at=detail.version.approved_at,
        days_project_management=calc.kpis.days_project_management,
        days_delivery=calc.kpis.days_delivery,
        days_total=calc.kpis.days_total,
        phases=phases,
        total_revenue=calc.kpis.price_project,
        outcome=detail.outcome.value if detail.outcome else None,
    )
