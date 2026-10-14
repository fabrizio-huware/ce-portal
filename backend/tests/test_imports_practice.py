"""Importazione CSV dei collaboratori con la colonna Practice."""

from sqlalchemy import select

from app.models import DEFAULT_PRACTICE, Employee, Practice
from tests.factories import make_practice, make_profile, make_user
from tests.helpers import auth
from tests.test_imports_api import EMP_URL, count, upload


def _setup(session):
    h = auth(make_user(session, role="admin"))
    make_profile(session, name="Senior")
    make_practice(session, name="Cloud")
    make_practice(session, name="Data")
    make_practice(session, name="Vecchia", is_active=False)
    return h


def _practices(session) -> dict[str, str]:
    rows = session.execute(
        select(Employee.first_name, Practice.name).join(
            Practice, Practice.id == Employee.practice_id
        )
    )
    return {first: name for first, name in rows}


def _run(api, h, csv, dry_run=False):
    return api.post(f"{EMP_URL}?dry_run={'true' if dry_run else 'false'}", headers=h, **upload(csv))


def test_the_practice_column_assigns_the_practice_ignoring_case(api, session):
    h = _setup(session)
    csv = "Nome;Cognome;Profilo;Practice\nAda;L;Senior;cloud\nBruno;N;Senior;DATA\n"
    assert _run(api, h, csv).status_code == 200
    assert _practices(session) == {"Ada": "Cloud", "Bruno": "Data"}


def test_an_unknown_practice_blocks_everything_with_the_line_number(api, session):
    h = _setup(session)
    csv = "Nome;Cognome;Profilo;Practice\nAda;L;Senior;Cloud\nBruno;N;Senior;Inesistente\n"
    resp = _run(api, h, csv)
    body = resp.json()
    assert resp.status_code == 422 and [e["line"] for e in body["errors"]] == [3]
    assert (
        "Practice sconosciuta" in body["errors"][0]["message"]
        and "Inesistente" in body["errors"][0]["message"]
    )
    assert count(session, Employee) == 0  # nemmeno la riga corretta è stata scritta


def test_an_inactive_practice_is_an_error(api, session):
    h = _setup(session)
    body = _run(
        api, h, "Nome;Cognome;Profilo;Practice\nAda;L;Senior;Vecchia\n", dry_run=True
    ).json()
    assert "non è attiva" in body["errors"][0]["message"]


def test_without_the_column_or_with_an_empty_cell_new_employees_get_the_default(api, session):
    h = _setup(session)
    _run(api, h, "Nome;Cognome;Profilo\nAda;L;Senior\n")
    _run(api, h, "Nome;Cognome;Profilo;Practice\nBruno;N;Senior;\n")
    assert _practices(session) == {"Ada": DEFAULT_PRACTICE, "Bruno": DEFAULT_PRACTICE}


def test_existing_employees_keep_their_practice_when_the_file_does_not_say(api, session):
    h = _setup(session)
    _run(api, h, "Nome;Cognome;Profilo;Practice\nAda;L;Senior;Cloud\n")
    again = _run(
        api, h, "Nome;Cognome;Profilo\nAda;L;Senior\n"
    ).json()  # file vecchio, senza la colonna
    assert (again["created"], again["updated"], again["unchanged"]) == (0, 0, 1)
    empty = _run(
        api, h, "Nome;Cognome;Profilo;Practice\nAda;L;Senior;\n"
    ).json()  # cella vuota: non cambia
    assert empty["unchanged"] == 1 and _practices(session) == {"Ada": "Cloud"}


def test_the_file_can_move_an_existing_employee_and_the_preview_says_so(api, session):
    h = _setup(session)
    _run(api, h, "Nome;Cognome;Profilo;Practice\nAda;L;Senior;Cloud\n")
    csv = "Nome;Cognome;Profilo;Practice\nAda;L;Senior;Data\nNuovo;U;Senior;Cloud\n"
    preview = _run(api, h, csv, dry_run=True).json()
    assert (preview["created"], preview["updated"], preview["unchanged"]) == (1, 1, 0)
    assert _practices(session) == {"Ada": "Cloud"}  # l'anteprima non scrive
    _run(api, h, csv)
    assert _practices(session) == {"Ada": "Data", "Nuovo": "Cloud"}


def test_the_column_can_be_called_area(api, session):
    h = _setup(session)
    _run(api, h, "Nome;Cognome;Profilo;Area\nAda;L;Senior;Cloud\n")
    assert _practices(session) == {"Ada": "Cloud"}
