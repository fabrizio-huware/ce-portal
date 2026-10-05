from datetime import date

from sqlalchemy import func, select

from app.db import seed
from app.models import NonWorkingDay, Profile, ProfileRate


def _counts(session):
    return (
        session.scalar(select(func.count()).select_from(Profile)),
        session.scalar(select(func.count()).select_from(ProfileRate)),
        session.scalar(select(func.count()).select_from(NonWorkingDay)),
    )


def test_seed_loads_expected_data_and_is_idempotent(session):
    seed.seed_profiles(session)
    seed.seed_non_working_days(session)
    assert _counts(session) == (8, 8, 26)
    seed.seed_profiles(session)
    seed.seed_non_working_days(session)
    assert _counts(session) == (8, 8, 26)


def test_seed_rates_match_the_spreadsheet(session):
    seed.seed_profiles(session)
    rows = session.execute(
        select(Profile.name, ProfileRate.daily_price, ProfileRate.daily_cost)
        .join(ProfileRate, ProfileRate.profile_id == Profile.id)
        .where(ProfileRate.year == 2026)
    ).all()
    rates = {name: (float(price), float(cost)) for name, price, cost in rows}
    assert rates["Partner"] == (1800.0, 1000.0)
    assert rates["Senior"] == (850.0, 330.0)
    assert rates["Stage"] == (300.0, 66.0)
    assert "Esterni" not in rates


def test_seed_does_not_overwrite_admin_changes(session):
    seed.seed_profiles(session)
    session.execute(
        ProfileRate.__table__.update().where(ProfileRate.year == 2026).values(daily_price=9999)
    )
    seed.seed_profiles(session)
    prices = set(session.scalars(select(ProfileRate.daily_price)))
    assert prices == {9999}


def test_seed_includes_sant_ambrogio(session):
    seed.seed_non_working_days(session)
    assert (
        session.scalar(
            select(NonWorkingDay.description).where(NonWorkingDay.day == date(2026, 12, 7))
        )
        == "Sant'Ambrogio"
    )
