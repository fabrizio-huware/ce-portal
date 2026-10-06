"""Dashboard portfolio e carico risorse (solo admin e presale), con export."""

import uuid
from datetime import UTC, date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Response

from app.api.deps import EditorUser, SessionDep
from app.exports import dashboard_export
from app.exports.common import file_response, safe_filename
from app.schemas.dashboard import PortfolioOut, ResourcesOut
from app.services import audit, dashboards

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

ExportFormat = Annotated[Literal["xlsx", "csv"], Query(alias="format", description="xlsx o csv")]


def _check_period(date_from: date | None, date_to: date | None) -> None:
    if date_from and date_to and date_to < date_from:
        raise HTTPException(422, "La data finale precede quella iniziale")


def _portfolio(
    session, date_from, date_to, client_id, business_unit, include_pipeline
) -> PortfolioOut:
    _check_period(date_from, date_to)
    return dashboards.portfolio(
        session, date_from=date_from, date_to=date_to, client_id=client_id,
        business_unit=business_unit, include_pipeline=include_pipeline,
    )  # fmt: skip


def _resources(
    session, date_from, date_to, client_id, profile_id, employee_id, include_pipeline
) -> ResourcesOut:
    _check_period(date_from, date_to)
    try:
        return dashboards.resources(
            session,
            date_from=date_from,
            date_to=date_to,
            client_id=client_id,
            profile_id=profile_id,
            employee_id=employee_id,
            include_pipeline=include_pipeline,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


PERIOD_FROM = Annotated[
    date | None, Query(description="CE attivi dal... (periodo che si sovrappone)")
]
PERIOD_TO = Annotated[date | None, Query(description="...fino al")]


@router.get(
    "/portfolio", response_model=PortfolioOut, summary="Portfolio: approvati e, a parte, pipeline"
)
def get_portfolio(
    user: EditorUser,
    session: SessionDep,
    date_from: PERIOD_FROM = None,
    date_to: PERIOD_TO = None,
    client_id: uuid.UUID | None = None,
    business_unit: str | None = None,
    include_pipeline: Annotated[bool, Query(description="Aggiunge, separata, la pipeline")] = True,
) -> PortfolioOut:
    """Numero di CE, ricavi, costi, margine e giornate per cliente, business unit, stato e mese.
    Approvati = ultima versione approvata; pipeline = CE senza ancora una versione approvata."""
    return _portfolio(session, date_from, date_to, client_id, business_unit, include_pipeline)


@router.get(
    "/portfolio/export", summary="Esporta il portfolio (Excel: tutte le tabelle; CSV: elenco CE)"
)
def export_portfolio(
    user: EditorUser,
    session: SessionDep,
    fmt: ExportFormat = "xlsx",
    date_from: PERIOD_FROM = None,
    date_to: PERIOD_TO = None,
    client_id: uuid.UUID | None = None,
    business_unit: str | None = None,
    include_pipeline: bool = True,
) -> Response:
    data = _portfolio(session, date_from, date_to, client_id, business_unit, include_pipeline)
    content = (
        dashboard_export.portfolio_xlsx(data)
        if fmt == "xlsx"
        else dashboard_export.portfolio_csv(data)
    )
    audit.record(
        session,
        user,
        "report",
        None,
        "export",
        {"report": "portfolio", "format": fmt, "rows": len(data.items)},
    )
    session.commit()
    return file_response(
        content, fmt, safe_filename("portfolio_ce", datetime.now(UTC).strftime("%Y%m%d"), ext=fmt)
    )


@router.get(
    "/resources",
    response_model=ResourcesOut,
    summary="Carico risorse per mese, collaboratore e profilo",
)
def get_resources(
    user: EditorUser,
    session: SessionDep,
    date_from: PERIOD_FROM = None,
    date_to: PERIOD_TO = None,
    client_id: uuid.UUID | None = None,
    profile_id: uuid.UUID | None = None,
    employee_id: uuid.UUID | None = None,
    include_pipeline: Annotated[bool, Query(description="Include anche la pipeline")] = False,
) -> ResourcesOut:
    """Giorni, ore e FTE per mese. Capacità = giorni lavorativi del calendario generale.

    Un collaboratore è sovraccarico se supera il 100% (1 FTE) in un mese.
    Senza date: dal mese corrente a 11 mesi dopo."""
    return _resources(
        session, date_from, date_to, client_id, profile_id, employee_id, include_pipeline
    )


@router.get("/resources/export", summary="Esporta il carico risorse")
def export_resources(
    user: EditorUser,
    session: SessionDep,
    fmt: ExportFormat = "xlsx",
    date_from: PERIOD_FROM = None,
    date_to: PERIOD_TO = None,
    client_id: uuid.UUID | None = None,
    profile_id: uuid.UUID | None = None,
    employee_id: uuid.UUID | None = None,
    include_pipeline: bool = False,
) -> Response:
    data = _resources(
        session, date_from, date_to, client_id, profile_id, employee_id, include_pipeline
    )
    content = (
        dashboard_export.resources_xlsx(data)
        if fmt == "xlsx"
        else dashboard_export.resources_csv(data)
    )
    audit.record(
        session,
        user,
        "report",
        None,
        "export",
        {"report": "resources", "format": fmt, "months": len(data.months)},
    )
    session.commit()
    return file_response(
        content, fmt, safe_filename("carico_risorse", datetime.now(UTC).strftime("%Y%m%d"), ext=fmt)
    )
