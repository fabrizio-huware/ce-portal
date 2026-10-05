"""Ogni regola di integrità concordata nell'analisi deve essere imposta dal database."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError

from app.models import (
    AuditLog,
    CELine,
    CELineAllocation,
    CEMilestone,
    CEPhase,
    CEVersion,
    CEVersionRate,
    Client,
    EmailOutbox,
    Employee,
    NonWorkingDay,
    Profile,
    ProfileRate,
    User,
)
from tests.factories import (
    approved_fields,
    assert_rejected,
    make_ce,
    make_client,
    make_internal_line,
    make_phase,
    make_profile,
    make_user,
    make_version,
    n,
)


# ---------- utenti e anagrafiche ----------
def test_user_role_must_be_valid(session):
    assert_rejected(
        session, "ck_users_role_valid", User(email="a@huware.com", full_name="A", role="boss")
    )


def test_user_email_must_be_lowercase_and_unique(session):
    assert_rejected(
        session,
        "ck_users_email_lowercase",
        User(email="A@Huware.com", full_name="A", role="viewer"),
    )
    session.add(User(email="dup@huware.com", full_name="A", role="viewer"))
    session.flush()
    assert_rejected(
        session, "uq_users_email", User(email="dup@huware.com", full_name="B", role="viewer")
    )


def test_client_name_unique_case_insensitive(session):
    make_client(session, name="Menarini")
    assert_rejected(session, "uq_clients_name_lower", Client(name="MENARINI"))


def test_profile_rate_rules(session):
    profile = make_profile(session)
    session.add(ProfileRate(profile_id=profile.id, year=2026, daily_price=100, daily_cost=50))
    session.flush()
    assert_rejected(
        session,
        "pk_profile_rates",
        ProfileRate(profile_id=profile.id, year=2026, daily_price=1, daily_cost=1),
    )
    assert_rejected(
        session,
        "ck_profile_rates_price_non_negative",
        ProfileRate(profile_id=profile.id, year=2027, daily_price=-1, daily_cost=1),
    )
    assert_rejected(
        session,
        "ck_profile_rates_cost_non_negative",
        ProfileRate(profile_id=profile.id, year=2028, daily_price=1, daily_cost=-1),
    )


def test_profile_in_use_cannot_be_deleted(session):
    profile = make_profile(session)
    session.add(Employee(first_name="Ada", last_name="Rossi", default_profile_id=profile.id))
    session.flush()
    with pytest.raises(IntegrityError):
        with session.begin_nested():
            session.execute(delete(Profile).where(Profile.id == profile.id))


def test_non_working_day_kind_and_uniqueness(session):
    session.add(NonWorkingDay(day=date(2026, 12, 24), kind="company_closure", description="x"))
    session.flush()
    assert_rejected(
        session,
        "uq_non_working_days_day",
        NonWorkingDay(day=date(2026, 12, 24), kind="holiday", description="y"),
    )
    assert_rejected(
        session,
        "ck_non_working_days_kind_valid",
        NonWorkingDay(day=date(2026, 12, 31), kind="ponte", description="z"),
    )


# ---------- CE e versioni ----------
@pytest.fixture
def base(session):
    user = make_user(session)
    client = make_client(session)
    ce = make_ce(session, user)
    return user, client, ce


def test_ce_code_unique_case_insensitive(session, base):
    user, _, _ = base
    make_ce(session, user, code="PS-MENAR-AI")
    from app.models import CE

    assert_rejected(session, "uq_ce_code_lower", CE(code="ps-menar-ai", created_by=user.id))


def test_version_dates_and_status_and_mode(session, base):
    user, client, ce = base
    kw = {"ce_id": ce.id, "client_id": client.id, "created_by": user.id}
    common = {
        "project_name": "P",
        "start_date": date(2026, 9, 1),
        "end_date": date(2027, 8, 31),
        "planning_mode": "hours",
        "rate_year": 2026,
        "version_number": 1,
    }
    bad_dates = {**common, "start_date": date(2027, 1, 2), "end_date": date(2027, 1, 1)}
    assert_rejected(session, "ck_ce_versions_dates_ordered", CEVersion(**kw, **bad_dates))
    assert_rejected(
        session, "ck_ce_versions_status_valid", CEVersion(**kw, **common, status="lost")
    )
    bad_mode = {**common, "planning_mode": "days"}
    assert_rejected(session, "ck_ce_versions_planning_mode_valid", CEVersion(**kw, **bad_mode))
    bad_number = {**common, "version_number": 0}
    assert_rejected(
        session, "ck_ce_versions_version_number_positive", CEVersion(**kw, **bad_number)
    )


def test_approved_version_requires_approver_and_totals(session, base):
    user, client, ce = base
    assert_rejected(
        session,
        "ck_ce_versions_approved_fields",
        CEVersion(
            ce_id=ce.id,
            version_number=1,
            status="approved",
            client_id=client.id,
            project_name="P",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 1),
            planning_mode="hours",
            rate_year=2026,
            created_by=user.id,
        ),
    )
    ok = make_version(session, ce, user, client, **approved_fields(user))
    assert ok.status == "approved"


def test_rejected_version_requires_who_and_when(session, base):
    user, client, ce = base
    assert_rejected(
        session,
        "ck_ce_versions_rejected_fields",
        CEVersion(
            ce_id=ce.id,
            version_number=1,
            status="rejected",
            client_id=client.id,
            project_name="P",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 1),
            planning_mode="hours",
            rate_year=2026,
            created_by=user.id,
        ),
    )


def test_only_one_open_version_per_ce(session, base):
    user, client, ce = base
    make_version(session, ce, user, client, version_number=1, **approved_fields(user))
    make_version(session, ce, user, client, version_number=2, status="draft")  # ok: v1 approvata
    assert_rejected(
        session,
        "uq_ce_versions_one_open",
        CEVersion(
            ce_id=ce.id,
            version_number=3,
            status="submitted",
            client_id=client.id,
            project_name="P",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 1),
            planning_mode="hours",
            rate_year=2026,
            created_by=user.id,
        ),
    )


def test_version_number_unique_per_ce(session, base):
    user, client, ce = base
    make_version(session, ce, user, client, version_number=1, **approved_fields(user))
    assert_rejected(
        session,
        "uq_ce_versions_ce_id",
        CEVersion(
            ce_id=ce.id,
            version_number=1,
            status="approved",
            approved_by=user.id,
            approved_at=func.now(),
            approved_totals={},
            client_id=client.id,
            project_name="P",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 1),
            planning_mode="hours",
            rate_year=2026,
            created_by=user.id,
        ),
    )


def test_client_in_use_cannot_be_deleted(session, base):
    user, client, ce = base
    make_version(session, ce, user, client)
    with pytest.raises(IntegrityError):
        with session.begin_nested():
            session.execute(delete(Client).where(Client.id == client.id))


def test_phase_contingency_range(session, base):
    user, client, ce = base
    version = make_version(session, ce, user, client)
    assert_rejected(
        session,
        "ck_ce_phases_contingency_range",
        CEPhase(version_id=version.id, position=1, name="F", contingency_pct=Decimal("100.01")),
    )


# ---------- righe ----------
@pytest.fixture
def phase_and_profile(session, base):
    user, client, ce = base
    version = make_version(session, ce, user, client)
    return make_phase(session, version), make_profile(session), version


def _line(phase, **kw):
    values = {"phase_id": phase.id, "position": 1, "activity": "Attività"}
    values.update(kw)
    return CELine(**values)


def test_internal_line_rules(session, phase_and_profile):
    phase, profile, _ = phase_and_profile
    ok = make_internal_line(session, phase, profile, hours=Decimal("16"))
    assert ok.is_project_management is False
    assert_rejected(session, "ck_ce_lines_line_shape", _line(phase, line_type="internal"))
    assert_rejected(
        session,
        "ck_ce_lines_line_shape",
        _line(phase, line_type="internal", profile_id=profile.id, external_cost=10),
    )
    assert_rejected(
        session,
        "ck_ce_lines_hours_non_negative",
        _line(phase, line_type="internal", profile_id=profile.id, hours=-1),
    )


def test_external_line_rules(session, phase_and_profile):
    phase, profile, _ = phase_and_profile
    session.add(_line(phase, line_type="external", external_cost=500, external_revenue=800))
    session.flush()
    shape = "ck_ce_lines_line_shape"
    assert_rejected(
        session,
        shape,
        _line(
            phase, line_type="external", profile_id=profile.id, external_cost=1, external_revenue=2
        ),
    )
    assert_rejected(session, shape, _line(phase, line_type="external", external_cost=1))
    assert_rejected(
        session,
        shape,
        _line(
            phase,
            line_type="external",
            external_cost=1,
            external_revenue=2,
            is_project_management=True,
        ),
    )
    assert_rejected(
        session,
        shape,
        _line(phase, line_type="external", external_cost=1, external_revenue=2, hours=8),
    )


def test_line_type_must_be_valid(session, phase_and_profile):
    phase, _, _ = phase_and_profile
    # Un tipo sconosciuto viola sia line_type_valid sia line_shape: PostgreSQL ne segnala uno.
    assert_rejected(session, "ck_ce_lines_line_", _line(phase, line_type="altro"))


# ---------- allocazioni e milestone ----------
def test_allocation_rules(session, phase_and_profile):
    phase, profile, _ = phase_and_profile
    line = make_internal_line(session, phase, profile)
    session.add(CELineAllocation(line_id=line.id, month=date(2026, 9, 1), allocation_pct=100))
    session.flush()
    assert_rejected(
        session,
        "pk_ce_line_allocations",
        CELineAllocation(line_id=line.id, month=date(2026, 9, 1), allocation_pct=50),
    )
    assert_rejected(
        session,
        "ck_ce_line_allocations_allocation_pct_range",
        CELineAllocation(line_id=line.id, month=date(2026, 10, 1), allocation_pct=100.01),
    )
    assert_rejected(
        session,
        "ck_ce_line_allocations_allocation_pct_range",
        CELineAllocation(line_id=line.id, month=date(2026, 10, 1), allocation_pct=-1),
    )
    assert_rejected(
        session,
        "ck_ce_line_allocations_month_first_day",
        CELineAllocation(line_id=line.id, month=date(2026, 11, 15), allocation_pct=10),
    )


def test_milestone_month_and_uniqueness(session, phase_and_profile):
    *_, version = phase_and_profile
    session.add(CEMilestone(version_id=version.id, month=date(2026, 10, 1), label="Kick-off"))
    session.flush()
    assert_rejected(
        session,
        "uq_ce_milestones_version_id",
        CEMilestone(version_id=version.id, month=date(2026, 10, 1), label="Kick-off"),
    )
    assert_rejected(
        session,
        "ck_ce_milestones_month_first_day",
        CEMilestone(version_id=version.id, month=date(2026, 10, 9), label="GoLive"),
    )


def test_version_rates_are_not_negative(session, phase_and_profile):
    _, profile, version = phase_and_profile
    assert_rejected(
        session,
        "ck_ce_version_rates_price_non_negative",
        CEVersionRate(version_id=version.id, profile_id=profile.id, daily_price=-1, daily_cost=1),
    )


# ---------- cancellazioni a cascata ----------
def test_deleting_a_draft_version_removes_its_content(session, phase_and_profile):
    phase, profile, version = phase_and_profile
    line = make_internal_line(session, phase, profile)
    session.add_all(
        [
            CELineAllocation(line_id=line.id, month=date(2026, 9, 1), allocation_pct=50),
            CEVersionRate(
                version_id=version.id, profile_id=profile.id, daily_price=1, daily_cost=1
            ),
            CEMilestone(version_id=version.id, month=date(2026, 9, 1), label="M"),
        ]
    )
    session.flush()
    session.execute(delete(CEVersion).where(CEVersion.id == version.id))
    for model in (CEPhase, CELine, CELineAllocation, CEVersionRate, CEMilestone):
        assert session.scalar(select(func.count()).select_from(model)) == 0, model.__name__


def test_hard_deleting_a_ce_with_versions_is_blocked(session, base):
    user, client, ce = base
    make_version(session, ce, user, client)
    with pytest.raises(IntegrityError):
        with session.begin_nested():
            session.execute(text("DELETE FROM ce WHERE id = :i"), {"i": ce.id})


# ---------- audit ed email ----------
def test_audit_log_survives_user_deletion(session):
    user = make_user(session, email=f"tmp{n()}@huware.com")
    entry = AuditLog(user_id=user.id, entity_type="ce", action="create", changes={"a": 1})
    session.add(entry)
    session.flush()
    session.execute(delete(User).where(User.id == user.id))
    session.refresh(entry)
    assert entry.user_id is None
    assert entry.id is not None


def test_email_outbox_defaults_and_status(session):
    mail = EmailOutbox(type="ce_submitted", recipient="x@huware.com", payload={"ce": "A"})
    session.add(mail)
    session.flush()
    session.refresh(mail)
    assert (mail.status, mail.attempts) == ("pending", 0)
    assert_rejected(
        session,
        "ck_email_outbox_status_valid",
        EmailOutbox(type="t", recipient="x@huware.com", payload={}, status="lost"),
    )
