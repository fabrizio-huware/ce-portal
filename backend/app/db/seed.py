"""Dati iniziali. Idempotente: si può rieseguire senza duplicare né sovrascrivere modifiche."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.calendar import holidays_for_year
from app.models import NonWorkingDay, Profile, ProfileRate

RATES_YEAR = 2026
HOLIDAY_YEARS = (2026, 2027)

# (nome, prezzo/giorno, costo/giorno, billability target %) dal foglio "EC - COSTO AZIENDALE".
# Il profilo "Esterni" non è incluso: le righe esterne hanno costo e ricavo liberi.
# Le bande non sono importate (nel foglio risultano duplicate): l'admin potrà valorizzarle.
PROFILES = [
    ("Partner", "1800.00", "1000.00", None),
    ("Manager", "1200.00", "800.00", "40"),
    ("Practice", "1000.00", "540.00", "70"),
    ("Solutions / Leader", "900.00", "440.00", "80"),
    ("Senior", "850.00", "330.00", "80"),
    ("Specialist", "725.00", "280.00", "90"),
    ("Consultant", "650.00", "250.00", "90"),
    ("Stage", "300.00", "66.00", "30"),
]


def seed_profiles(session: Session) -> None:
    for order, (name, price, cost, target) in enumerate(PROFILES, start=1):
        session.execute(
            insert(Profile)
            .values(
                name=name,
                sort_order=order * 10,
                billability_target=Decimal(target) if target else None,
            )
            .on_conflict_do_nothing(index_elements=["name"])
        )
        profile_id = session.scalar(select(Profile.id).where(Profile.name == name))
        session.execute(
            insert(ProfileRate)
            .values(
                profile_id=profile_id,
                year=RATES_YEAR,
                daily_price=Decimal(price),
                daily_cost=Decimal(cost),
            )
            .on_conflict_do_nothing(index_elements=["profile_id", "year"])
        )


def seed_non_working_days(session: Session, years: tuple[int, ...] = HOLIDAY_YEARS) -> None:
    for year in years:
        for day, description in holidays_for_year(year):
            session.execute(
                insert(NonWorkingDay)
                .values(day=day, kind="holiday", description=description)
                .on_conflict_do_nothing(index_elements=["day"])
            )


def run(session: Session) -> None:
    seed_profiles(session)
    seed_non_working_days(session)
    session.commit()


if __name__ == "__main__":
    from app.db.session import SessionLocal

    with SessionLocal() as s:
        run(s)
    print("Dati iniziali caricati.")
