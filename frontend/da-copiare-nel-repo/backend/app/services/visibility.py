"""Chi vede quali CE: la visibilità per business unit.

Con l'interruttore **acceso**, un presale o un responsabile di business unit vede un CE se ne è
l'autore oppure se la sua business unit è tra quelle coinvolte, e lo vede per intero. Gli
amministratori vedono tutto; viewer e integrazioni non cambiano. Con l'interruttore **spento**
(come alla pubblicazione) nulla cambia.
Un CE che non si vede risponde «non trovato»: non si scopre nemmeno che esiste.
"""

import uuid

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    CE,
    DEFAULT_BUSINESS_UNIT,
    AppSetting,
    BusinessUnit,
    CEBusinessUnit,
    Employee,
    Practice,
    User,
)
from app.models.accounts import AUTHOR_ROLES
from app.services import audit

SETTING_KEY = "bu_visibility_enabled"
_SETTING_ID = uuid.uuid5(
    uuid.NAMESPACE_URL, f"setting:{SETTING_KEY}"
)  # per il registro delle modifiche


def is_enabled(session: Session) -> bool:
    row = session.get(AppSetting, SETTING_KEY)
    return bool(row is not None and row.value is True)


def set_enabled(session: Session, actor: User, enabled: bool) -> None:
    row = session.get(AppSetting, SETTING_KEY)
    before = bool(row is not None and row.value is True)
    if row is None:
        session.add(AppSetting(key=SETTING_KEY, value=enabled, updated_by=actor.id))
    else:
        row.value = enabled
        row.updated_by = actor.id
    if before != enabled:
        audit.record(
            session, actor, "setting", _SETTING_ID, "update", {SETTING_KEY: [before, enabled]}
        )
    session.commit()


def is_scoped(session: Session, user: User) -> bool:
    """Vale la regola per questo utente (presale o responsabile, interruttore acceso)?"""
    return user.role in AUTHOR_ROLES and is_enabled(session)


def visible_condition(session: Session, user: User):
    """Condizione SQL sui CE visibili all'utente, o `None` se li vede tutti."""
    if not is_scoped(session, user):
        return None
    mine = CE.created_by == user.id
    if user.business_unit_id is None:
        return mine
    involved = select(CEBusinessUnit.ce_id).where(
        CEBusinessUnit.business_unit_id == user.business_unit_id
    )
    return or_(mine, CE.id.in_(involved))


def ensure_can_see(session: Session, user: User, ce_id: uuid.UUID) -> None:
    """`404` (lo stesso di un CE che non esiste) se il CE esiste ma l'utente non lo vede."""
    condition = visible_condition(session, user)
    if condition is None:
        return
    if session.scalar(select(CE.id).where(CE.id == ce_id)) is None:
        return  # non esiste: risponde 404 la rotta stessa
    if session.scalar(select(CE.id).where(CE.id == ce_id, condition)) is None:
        raise HTTPException(404, "CE non trovato")


def scope_unit_ids(session: Session, user: User) -> set[uuid.UUID] | None:
    """Business unit di cui l'utente vede persone e practice nel carico risorse (`None` = tutte)."""
    if not is_scoped(session, user):
        return None
    return {user.business_unit_id} if user.business_unit_id else set()


def employees_of(session: Session, unit_ids: set[uuid.UUID]) -> set[uuid.UUID]:
    """Collaboratori le cui practice stanno nelle business unit indicate."""
    if not unit_ids:
        return set()
    return set(
        session.scalars(
            select(Employee.id)
            .join(Practice, Practice.id == Employee.practice_id)
            .where(Practice.business_unit_id.in_(unit_ids))
        )
    )


def report(session: Session) -> dict:
    """Che cosa manca prima di accendere l'interruttore."""
    declared = select(CEBusinessUnit.ce_id)
    without = (
        select(CE.id, CE.code)
        .where(CE.deleted_at.is_(None), CE.id.not_in(declared))
        .order_by(func.lower(CE.code))
    )
    rows = session.execute(without).all()
    people = session.scalars(
        select(User.full_name)
        .where(
            User.is_active,
            User.is_service.is_(False),
            User.role.in_(AUTHOR_ROLES),
            User.business_unit_id.is_(None),
        )
        .order_by(func.lower(User.full_name))
    ).all()
    unassigned = (
        session.scalar(
            select(func.count(Practice.id))
            .join(BusinessUnit, BusinessUnit.id == Practice.business_unit_id)
            .where(
                Practice.is_active,
                func.lower(BusinessUnit.name) == DEFAULT_BUSINESS_UNIT.lower(),
            )
        )
        or 0
    )
    return {
        "ces_without_business_units": len(rows),
        "ces_without_examples": [{"ce_id": r[0], "code": r[1]} for r in rows[:20]],
        "people_without_business_unit": list(people),
        "practices_unassigned": unassigned,
    }
