"""Ogni collaboratore ha una practice: «Da assegnare» se non indicata, modificabile, sempre una practice attiva."""

from sqlalchemy import func, select

from app.models import DEFAULT_PRACTICE, AuditLog, Employee, Practice
from tests.factories import make_practice, make_profile, make_user
from tests.helpers import auth

URL = "/api/v1/employees"


def _setup(session):
    return auth(make_user(session, role="admin")), make_profile(session, name="Senior")


def _create(api, h, profile, first="Mario", **kw):
    body = {"first_name": first, "last_name": "Rossi", "default_profile_id": str(profile.id), **kw}
    return api.post(URL, headers=h, json=body)


def _named(session, name) -> Practice:
    return session.scalar(select(Practice).where(func.lower(Practice.name) == name.lower()))


def test_without_a_practice_the_employee_gets_the_default_one(api, session):
    h, profile = _setup(session)
    body = _create(api, h, profile).json()
    assert body["practice_name"] == DEFAULT_PRACTICE
    assert body["practice_id"] == str(_named(session, DEFAULT_PRACTICE).id)


def test_the_default_practice_is_reused_not_duplicated(api, session):
    h, profile = _setup(session)
    for first in ("Ada", "Bruno", "Carla"):
        assert _create(api, h, profile, first=first).status_code == 201
    assert (
        session.scalar(
            select(func.count())
            .select_from(Practice)
            .where(func.lower(Practice.name) == "da assegnare")
        )
        == 1
    )


def test_an_employee_can_be_created_with_a_practice(api, session):
    h, profile = _setup(session)
    cloud = make_practice(session, name="Cloud")
    body = _create(api, h, profile, practice_id=str(cloud.id)).json()
    assert (body["practice_id"], body["practice_name"]) == (str(cloud.id), "Cloud")


def test_unknown_or_inactive_practice_is_rejected_on_creation(api, session):
    h, profile = _setup(session)
    old = make_practice(session, name="Vecchia", is_active=False)
    assert _create(api, h, profile, practice_id=str(old.id)).status_code == 422
    resp = _create(api, h, profile, practice_id="00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 422 and "non trovata" in resp.json()["detail"]
    assert session.scalar(select(func.count()).select_from(Employee)) == 0  # nulla è stato scritto


def test_the_practice_can_be_changed_but_never_emptied(api, session):
    h, profile = _setup(session)
    cloud, data = make_practice(session, name="Cloud"), make_practice(session, name="Data")
    emp = _create(api, h, profile, practice_id=str(cloud.id)).json()
    ok = api.patch(f"{URL}/{emp['id']}", headers=h, json={"practice_id": str(data.id)})
    assert ok.status_code == 200 and ok.json()["practice_name"] == "Data"
    empty = api.patch(f"{URL}/{emp['id']}", headers=h, json={"practice_id": None})
    assert empty.status_code == 422 and "practice_id" in empty.json()["detail"]
    assert api.get(f"{URL}/{emp['id']}", headers=h).json()["practice_name"] == "Data"


def test_a_deactivated_practice_cannot_be_chosen_but_does_not_block_other_edits(api, session):
    h, profile = _setup(session)
    cloud, old = make_practice(session, name="Cloud"), make_practice(session, name="Vecchia")
    emp = _create(api, h, profile, practice_id=str(old.id)).json()
    old.is_active = False
    session.flush()
    assert (
        api.patch(f"{URL}/{emp['id']}", headers=h, json={"practice_id": str(old.id)}).status_code
        == 200
    )  # invariata
    assert (
        api.patch(f"{URL}/{emp['id']}", headers=h, json={"first_name": "Marco"}).status_code == 200
    )
    other = api.patch(f"{URL}/{emp['id']}", headers=h, json={"practice_id": str(cloud.id)})
    assert other.status_code == 200
    back = api.patch(f"{URL}/{emp['id']}", headers=h, json={"practice_id": str(old.id)})
    assert back.status_code == 422 and "non è attiva" in back.json()["detail"]


def test_the_list_can_be_filtered_by_practice(api, session):
    h, profile = _setup(session)
    cloud, data = make_practice(session, name="Cloud"), make_practice(session, name="Data")
    _create(api, h, profile, first="Ada", practice_id=str(cloud.id))
    _create(api, h, profile, first="Bruno", practice_id=str(data.id))
    _create(api, h, profile, first="Carla")  # «Da assegnare»
    names = lambda r: sorted(e["first_name"] for e in r.json()["items"])  # noqa: E731
    assert names(api.get(f"{URL}?practice_id={cloud.id}", headers=h)) == ["Ada"]
    assert names(api.get(f"{URL}?practice_id={data.id}", headers=h)) == ["Bruno"]
    assert names(api.get(URL, headers=h)) == ["Ada", "Bruno", "Carla"]
    items = api.get(URL, headers=h).json()["items"]
    assert {e["first_name"]: e["practice_name"] for e in items} == {
        "Ada": "Cloud",
        "Bruno": "Data",
        "Carla": DEFAULT_PRACTICE,
    }


def test_any_way_of_inserting_an_employee_gets_a_practice(session):
    """Anche un inserimento diretto (script, importazione) non può produrre un collaboratore senza practice."""
    profile = make_profile(session, name="Senior")
    emp = Employee(first_name="Diretto", last_name="Test", default_profile_id=profile.id)
    session.add(emp)
    session.flush()
    assert emp.practice_id is not None
    assert session.get(Practice, emp.practice_id).name == DEFAULT_PRACTICE


def test_the_audit_log_records_the_effective_practice_on_creation_and_on_change(api, session):
    h, profile = _setup(session)
    data = make_practice(session, name="Data")
    emp = _create(api, h, profile).json()  # senza practice: «Da assegnare»
    api.patch(f"{URL}/{emp['id']}", headers=h, json={"practice_id": str(data.id)})
    entries = session.scalars(
        select(AuditLog).where(AuditLog.entity_type == "employee").order_by(AuditLog.id)
    ).all()
    assert (
        str(entries[0].changes["practice_id"]) == emp["practice_id"]
    )  # quella assegnata, non «nessuna»
    assert "practice_id" in entries[1].changes
