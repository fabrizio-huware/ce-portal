"""I file CSV di esempio in docs/esempi devono essere importabili senza errori."""

from pathlib import Path

from sqlalchemy import func, select

from app.models import Employee, NonWorkingDay, Profile, ProfileRate
from tests.factories import make_user
from tests.helpers import auth

EXAMPLES = Path(__file__).resolve().parents[2] / "docs" / "esempi"


def _upload(name):
    return {"files": {"file": (name, (EXAMPLES / name).read_bytes(), "text/csv")}}


def test_example_files_import_cleanly_in_order(api, session):
    h = auth(make_user(session, role="admin"))

    rates = api.post(
        "/api/v1/profiles/import-rates?dry_run=false", headers=h, **_upload("listino.csv")
    )
    assert rates.status_code == 200, rates.text
    assert rates.json()["created"] == 9 and rates.json()["extra"]["profili_creati"] == 9

    people = api.post(
        "/api/v1/employees/import?dry_run=false", headers=h, **_upload("collaboratori.csv")
    )
    assert people.status_code == 200, people.text
    assert people.json()["created"] == 4

    closures = api.post(
        "/api/v1/calendar/import?dry_run=false", headers=h, **_upload("chiusure.csv")
    )
    assert closures.status_code == 200, closures.text
    assert closures.json()["created"] == 2

    count = lambda model: session.scalar(select(func.count()).select_from(model))  # noqa: E731
    assert (count(Profile), count(ProfileRate), count(Employee), count(NonWorkingDay)) == (
        9,
        9,
        4,
        2,
    )
    esterni = session.scalar(select(Profile).where(Profile.name == "Esterni"))
    assert esterni.is_external is True  # riconosciuto dal nome, senza colonna dedicata
    partner = session.scalar(select(ProfileRate).join(Profile).where(Profile.name == "Partner"))
    assert (float(partner.daily_price), float(partner.daily_cost)) == (1800.0, 1000.0)
