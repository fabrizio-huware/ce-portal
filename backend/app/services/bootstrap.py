"""Creazione del primo amministratore, solo se non esiste ancora nessun utente."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import User
from app.services import audit


def ensure_bootstrap_admin(session: Session, email: str | None) -> User | None:
    if not email:
        return None
    if (session.scalar(select(func.count()).select_from(User)) or 0) > 0:
        return None
    user = User(email=email.lower(), full_name="Amministratore", role="admin")
    session.add(user)
    session.flush()
    audit.record(session, None, "user", user.id, "bootstrap_admin", {"email": user.email})
    session.commit()
    return user
