"""Integrazioni: ciò che un programma esterno può leggere e fare, sempre senza costi né margini."""

import uuid
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exports.reduced import reduced_from_detail
from app.models import (
    CE,
    DEFAULT_BUSINESS_UNIT,
    BusinessUnit,
    CEVersion,
    Client,
    Employee,
    Integration,
    Profile,
    User,
)
from app.schemas.ce import CECreate
from app.schemas.integrations import (
    IntegrationCE,
    IntegrationCECreate,
    IntegrationCEItem,
    IntegrationContent,
    IntegrationPhase,
    LookupItem,
)
from app.services import audit
from app.services import ce as svc
from app.services.ce_search import CEFilters, apply_filters, latest_subquery

NOT_APPROVED_NOTICE = "Versione non approvata: i valori possono cambiare."


@dataclass
class Principal:
    """Chi sta chiamando: l'integrazione e il suo utente di servizio (autore dei CE che crea)."""

    integration: Integration
    user: User


# ======= elenchi di supporto: solo identificativo e nome
def clients(session: Session) -> list[LookupItem]:
    rows = session.scalars(select(Client).where(Client.is_active).order_by(func.lower(Client.name)))
    return [LookupItem(id=c.id, name=c.name) for c in rows]


def profiles(session: Session) -> list[LookupItem]:
    rows = session.scalars(
        select(Profile).where(Profile.is_active).order_by(func.lower(Profile.name))
    )
    return [LookupItem(id=p.id, name=p.name) for p in rows]


def business_units(session: Session) -> list[LookupItem]:
    """Business unit attive da indicare in creazione (la business unit di sistema non si offre)."""
    rows = session.scalars(
        select(BusinessUnit)
        .where(
            BusinessUnit.is_active, func.lower(BusinessUnit.name) != DEFAULT_BUSINESS_UNIT.lower()
        )
        .order_by(func.lower(BusinessUnit.name))
    )
    return [LookupItem(id=u.id, name=u.name) for u in rows]


def employees(session: Session) -> list[LookupItem]:
    rows = session.scalars(
        select(Employee)
        .where(Employee.is_active)
        .order_by(func.lower(Employee.last_name), func.lower(Employee.first_name))
    )
    return [LookupItem(id=e.id, name=f"{e.first_name} {e.last_name}") for e in rows]


# ======= CE
def _own(principal: Principal, ce: CE) -> bool:
    """Creato da questa integrazione (l'identificativo esterno resta suo dopo l'assegnazione)."""
    return ce.integration_id == principal.integration.id


def list_ce(
    session: Session,
    principal: Principal,
    f: CEFilters,
    *,
    status: str | None,
    external_ref: str | None,
    limit: int,
    offset: int,
) -> tuple[list[IntegrationCEItem], int]:
    """Ultima versione di ogni CE non eliminato, di qualunque stato."""
    latest = latest_subquery(only_approved=False)
    stmt = (
        select(CE, CEVersion, Client)
        .join(latest, latest.c.ce_id == CE.id)
        .join(CEVersion, and_(CEVersion.ce_id == CE.id, CEVersion.version_number == latest.c.n))
        .join(Client, Client.id == CEVersion.client_id)
        .where(CE.deleted_at.is_(None))
        .order_by(func.lower(CE.code))
    )
    stmt = apply_filters(stmt, f)
    if status:
        stmt = stmt.where(CEVersion.status == status)
    if external_ref:
        stmt = stmt.where(
            CE.integration_id == principal.integration.id, CE.external_ref == external_ref
        )
    total = session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = session.execute(stmt.limit(limit).offset(offset)).all()
    items = [
        IntegrationCEItem(
            ce_id=ce.id,
            code=ce.code,
            client_name=client.name,
            project_name=v.project_name,
            start_date=v.start_date,
            end_date=v.end_date,
            version_number=v.version_number,
            status=v.status,
            mine=ce.created_by == principal.user.id,
            external_ref=ce.external_ref if _own(principal, ce) else None,
        )
        for ce, v, client in rows
    ]
    return items, total


def summary(session: Session, principal: Principal, ce: CE) -> IntegrationCE:
    """Giornate e ricavi dell'ultima versione, di qualunque stato; mai costi, margini o tariffe."""
    version = svc.get_latest_version(session, ce)
    detail = svc.build_detail(session, principal.user, ce, version)
    reduced = reduced_from_detail(detail)
    own = _own(principal, ce)
    return IntegrationCE(
        ce_id=ce.id,
        code=ce.code,
        client_name=reduced.client_name,
        project_name=reduced.project_name,
        start_date=reduced.start_date,
        end_date=reduced.end_date,
        version_number=reduced.version_number,
        status=version.status,
        notice=None if version.status == "approved" else NOT_APPROVED_NOTICE,
        approved_at=version.approved_at,
        days_project_management=reduced.days_project_management,
        days_delivery=reduced.days_delivery,
        days_total=reduced.days_total,
        phases=[IntegrationPhase(name=p.name, revenue=p.revenue) for p in reduced.phases],
        total_revenue=reduced.total_revenue,
        mine=ce.created_by == principal.user.id,
        external_ref=ce.external_ref if own else None,
        requested_by=ce.requested_by if own else None,
    )


def own_content(session: Session, principal: Principal, ce: CE) -> IntegrationContent:
    """Il contenuto che l'integrazione ha inviato, riletto per poterlo correggere: nessun costo."""
    if ce.created_by != principal.user.id:
        raise HTTPException(
            403, "Il contenuto si rilegge solo per i CE di questa integrazione non ancora assegnati"
        )
    version = svc.get_latest_version(session, ce)
    content = svc.content_from_version(version).model_copy(
        update={"expected_revision": version.revision}
    )
    return IntegrationContent(
        revision=version.revision, status=version.status, content=content.model_dump(mode="json")
    )


def _existing(session: Session, principal: Principal, external_ref: str) -> CE | None:
    return session.scalar(
        select(CE).where(
            CE.integration_id == principal.integration.id, CE.external_ref == external_ref
        )
    )


def create_ce(session: Session, principal: Principal, body: IntegrationCECreate) -> tuple[CE, bool]:
    """Crea il CE con tutto il contenuto, tutto o niente. Con lo stesso identificativo esterno non
    crea un duplicato: restituisce quello già creato."""
    existing = _existing(session, principal, body.external_ref)
    if existing is not None:
        return existing, False
    user = principal.user
    header = body.content.header
    try:
        version = svc.create_ce(
            session,
            user,
            CECreate(
                code=body.code,
                standard_phases=False,
                business_unit_ids=body.business_unit_ids,
                **header.model_dump(),
            ),
            commit=False,
        )
        ce = svc.get_ce(session, version.ce_id)
        ce.integration_id = principal.integration.id
        ce.external_ref = body.external_ref
        ce.requested_by = body.requested_by
        content = body.content.model_copy(update={"expected_revision": version.revision})
        svc.save_content(session, user, ce, version, content, commit=False)
        audit.record(
            session,
            user,
            "ce",
            ce.id,
            "create_by_integration",
            {
                "integration": principal.integration.name,
                "external_ref": body.external_ref,
                "requested_by": body.requested_by,
            },
        )
        session.commit()
    except HTTPException:
        session.rollback()
        raise
    except IntegrityError:  # due richieste uguali in contemporanea: vince la prima
        session.rollback()
        existing = _existing(session, principal, body.external_ref)
        if existing is None:
            raise HTTPException(
                409, "Esiste già un CE con questo codice o identificativo"
            ) from None
        return existing, False
    return ce, True


def revision_if_mine(session: Session, principal: Principal, ce: CE) -> int | None:
    if ce.created_by != principal.user.id:
        return None
    return svc.get_latest_version(session, ce).revision


def get_visible_ce(session: Session, ce_id: uuid.UUID) -> CE:
    return svc.get_ce(session, ce_id)  # i CE eliminati non esistono per le integrazioni
