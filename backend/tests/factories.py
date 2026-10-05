"""Funzioni di comodo per creare oggetti validi nei test."""

import itertools
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    CE,
    CELine,
    CEPhase,
    CEVersion,
    Client,
    Profile,
    User,
)

_counter = itertools.count(1)


def n() -> int:
    return next(_counter)


def make_user(session: Session, role: str = "presale", **kw) -> User:
    email = kw.pop("email", f"user{n()}@huware.com")
    user = User(email=email, full_name="Utente Test", role=role, **kw)
    session.add(user)
    session.flush()
    return user


def make_client(session: Session, **kw) -> Client:
    client = Client(name=kw.pop("name", f"Cliente {n()}"), **kw)
    session.add(client)
    session.flush()
    return client


def make_profile(session: Session, **kw) -> Profile:
    profile = Profile(name=kw.pop("name", f"Profilo {n()}"), **kw)
    session.add(profile)
    session.flush()
    return profile


def make_ce(session: Session, user: User, **kw) -> CE:
    ce = CE(code=kw.pop("code", f"PS-TEST-{n()}"), created_by=user.id, **kw)
    session.add(ce)
    session.flush()
    return ce


def make_version(session: Session, ce: CE, user: User, client: Client, **kw) -> CEVersion:
    values = {
        "ce_id": ce.id,
        "version_number": 1,
        "status": "draft",
        "client_id": client.id,
        "project_name": "Progetto di test",
        "start_date": date(2026, 9, 1),
        "end_date": date(2027, 8, 31),
        "planning_mode": "percent",
        "rate_year": 2026,
        "created_by": user.id,
    }
    values.update(kw)
    version = CEVersion(**values)
    session.add(version)
    session.flush()
    return version


def approved_fields(user: User) -> dict:
    return {
        "status": "approved",
        "approved_by": user.id,
        "approved_at": datetime.now(UTC),
        "approved_totals": {"revenue": "1000.00", "cost": "600.00"},
    }


def make_phase(session: Session, version: CEVersion, **kw) -> CEPhase:
    phase = CEPhase(version_id=version.id, position=kw.pop("position", 1), name="Fase 1", **kw)
    session.add(phase)
    session.flush()
    return phase


def make_internal_line(session: Session, phase: CEPhase, profile: Profile, **kw) -> CELine:
    line = CELine(
        phase_id=phase.id,
        position=1,
        line_type="internal",
        activity="Analisi",
        profile_id=profile.id,
        **kw,
    )
    session.add(line)
    session.flush()
    return line


def assert_rejected(session: Session, constraint: str, *objects) -> None:
    """Verifica che il database rifiuti gli oggetti indicando proprio il vincolo atteso."""
    with pytest.raises(IntegrityError) as exc:
        with session.begin_nested():
            session.add_all(objects)
            session.flush()
    assert constraint in str(exc.value), f"atteso vincolo {constraint}, ricevuto: {exc.value}"
