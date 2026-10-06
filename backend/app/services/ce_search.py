"""Ricerca dei CE: usata dagli elenchi e, con gli stessi filtri, dagli export."""

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.api.deps import like_pattern
from app.models import CE, CEVersion, Client, User
from app.schemas.ce import (
    CEListItem,
    UserRef,
    ViewerCE,
    ViewerListItem,
    ViewerPhase,
)
from app.schemas.clients import ClientRef


@dataclass
class CEFilters:
    client_id: uuid.UUID | None = None
    project: str | None = None
    code: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    status: str | None = None
    created_by: uuid.UUID | None = None
    include_deleted: bool = False

    def as_audit(self) -> dict:
        return {k: str(v) for k, v in vars(self).items() if v not in (None, False)}


def _dec(value) -> Decimal | None:
    return None if value is None else Decimal(value)


def latest_subquery(*, only_approved: bool):
    query = select(CEVersion.ce_id.label("ce_id"), func.max(CEVersion.version_number).label("n"))
    if only_approved:
        query = query.where(CEVersion.status == "approved")
    return query.group_by(CEVersion.ce_id).subquery()


def apply_filters(stmt, f: CEFilters):
    if f.client_id:
        stmt = stmt.where(CEVersion.client_id == f.client_id)
    if f.project:
        stmt = stmt.where(CEVersion.project_name.ilike(like_pattern(f.project), escape="\\"))
    if f.code:
        stmt = stmt.where(CE.code.ilike(like_pattern(f.code), escape="\\"))
    # "da - a": progetti attivi nel periodo, cioè con il periodo che si sovrappone (estremi inclusi)
    if f.date_to:
        stmt = stmt.where(CEVersion.start_date <= f.date_to)
    if f.date_from:
        stmt = stmt.where(CEVersion.end_date >= f.date_from)
    return stmt


def _page(session: Session, stmt, limit: int, offset: int):
    total = session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    return session.execute(stmt.limit(limit).offset(offset)).all(), total


def editor_items(
    session: Session, f: CEFilters, limit: int, offset: int = 0
) -> tuple[list[CEListItem], int]:
    """Ultima versione di ogni CE, con prezzo, margine % e giornate (solo admin e presale)."""
    latest = latest_subquery(only_approved=False)
    stmt = (
        select(CE, CEVersion, Client, User)
        .join(latest, latest.c.ce_id == CE.id)
        .join(CEVersion, and_(CEVersion.ce_id == CE.id, CEVersion.version_number == latest.c.n))
        .join(Client, Client.id == CEVersion.client_id)
        .join(User, User.id == CE.created_by)
        .order_by(CEVersion.updated_at.desc(), func.lower(CE.code))
    )
    if not f.include_deleted:
        stmt = stmt.where(CE.deleted_at.is_(None))
    stmt = apply_filters(stmt, f)
    if f.status:
        stmt = stmt.where(CEVersion.status == f.status)
    if f.created_by:
        stmt = stmt.where(CE.created_by == f.created_by)
    rows, total = _page(session, stmt, limit, offset)
    items = []
    for ce, v, client, owner in rows:
        summary = v.summary or {}
        items.append(
            CEListItem(
                ce_id=ce.id,
                code=ce.code,
                client=ClientRef.model_validate(client),
                project_name=v.project_name,
                start_date=v.start_date,
                end_date=v.end_date,
                planning_mode=v.planning_mode,
                version_number=v.version_number,
                status=v.status,
                owner=UserRef(id=owner.id, full_name=owner.full_name),
                updated_at=v.updated_at,
                deleted=ce.deleted_at is not None,
                price=_dec(summary.get("revenue")),
                margin_pct=_dec(summary.get("margin_pct")),
                days_total=_dec(summary.get("days_total")),
            )
        )
    return items, total


def viewer_items(
    session: Session, f: CEFilters, limit: int, offset: int = 0
) -> tuple[list[ViewerListItem], int]:
    """Ultima versione approvata di ogni CE: solo codice, cliente, progetto, date e prezzo."""
    latest = latest_subquery(only_approved=True)
    stmt = (
        select(CE, CEVersion, Client)
        .join(latest, latest.c.ce_id == CE.id)
        .join(CEVersion, and_(CEVersion.ce_id == CE.id, CEVersion.version_number == latest.c.n))
        .join(Client, Client.id == CEVersion.client_id)
        .where(CE.deleted_at.is_(None))
        .order_by(func.lower(CE.code))
    )
    stmt = apply_filters(stmt, f)
    rows, total = _page(session, stmt, limit, offset)
    items = [
        ViewerListItem(
            ce_id=ce.id,
            code=ce.code,
            client_name=client.name,
            project_name=v.project_name,
            start_date=v.start_date,
            end_date=v.end_date,
            version_number=v.version_number,
            approved_at=v.approved_at,
            price=_dec((v.approved_totals or {}).get("revenue")),
        )
        for ce, v, client in rows
    ]
    return items, total


def viewer_ce(session: Session, ce: CE) -> ViewerCE | None:
    """Vista ridotta dell'ultima versione approvata (None se non esiste): dai totali congelati."""
    from app.services import ce as svc

    version = svc.get_latest_approved(session, ce)
    if version is None:
        return None
    totals = version.approved_totals or {}
    client = session.get(Client, version.client_id)
    return ViewerCE(
        ce_id=ce.id,
        code=ce.code,
        client_name=client.name,
        project_name=version.project_name,
        start_date=version.start_date,
        end_date=version.end_date,
        version_number=version.version_number,
        approved_at=version.approved_at,
        days_project_management=Decimal(totals["days_project_management"]),
        days_delivery=Decimal(totals["days_delivery"]),
        days_total=Decimal(totals["days_total"]),
        phases=[
            ViewerPhase(name=p["name"], revenue=Decimal(p["revenue"])) for p in totals["phases"]
        ],
        total_revenue=Decimal(totals["revenue"]),
    )
