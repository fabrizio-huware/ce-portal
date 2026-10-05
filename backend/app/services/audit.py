"""Registro delle modifiche (audit log) e utilità per applicare/confrontare valori."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog, User


def jsonable(value: Any) -> Any:
    if isinstance(value, Decimal | uuid.UUID):
        return str(value)
    if isinstance(value, date | datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [jsonable(v) for v in value]
    return value


def record(
    session: Session,
    actor: User | None,
    entity_type: str,
    entity_id: uuid.UUID | None,
    action: str,
    changes: dict[str, Any] | None = None,
) -> None:
    session.add(
        AuditLog(
            user_id=actor.id if actor else None,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            changes=jsonable(changes) if changes is not None else None,
        )
    )


def apply_changes(obj: Any, values: dict[str, Any]) -> dict[str, list[Any]]:
    """Imposta i campi e restituisce {campo: [vecchio, nuovo]} per quelli che sono cambiati."""
    changes: dict[str, list[Any]] = {}
    for field, new in values.items():
        old = getattr(obj, field)
        if old != new:
            setattr(obj, field, new)
            changes[field] = [jsonable(old), jsonable(new)]
    return changes
