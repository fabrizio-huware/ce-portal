from sqlalchemy import select

from app.models import AuditLog, User
from app.services.bootstrap import ensure_bootstrap_admin
from tests.factories import make_user


def test_creates_first_admin_when_no_users_exist(session):
    user = ensure_bootstrap_admin(session, "Prima.Admin@Huware.com")
    assert user is not None
    assert (user.email, user.role, user.is_active) == ("prima.admin@huware.com", "admin", True)
    assert session.scalars(select(AuditLog.action)).all() == ["bootstrap_admin"]


def test_does_nothing_when_users_already_exist(session):
    make_user(session)
    assert ensure_bootstrap_admin(session, "admin@huware.com") is None
    assert session.scalar(select(User.id).where(User.email == "admin@huware.com")) is None


def test_does_nothing_without_configured_email(session):
    assert ensure_bootstrap_admin(session, None) is None
    assert ensure_bootstrap_admin(session, "") is None
    assert session.scalar(select(User.id)) is None


def test_is_idempotent(session):
    assert ensure_bootstrap_admin(session, "admin@huware.com") is not None
    assert ensure_bootstrap_admin(session, "admin@huware.com") is None
    assert len(session.scalars(select(User.id)).all()) == 1
