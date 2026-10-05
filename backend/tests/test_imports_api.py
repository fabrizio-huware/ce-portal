from datetime import date
from decimal import Decimal

from sqlalchemy import func, select

from app.models import AuditLog, Employee, NonWorkingDay, Profile, ProfileRate
from tests.factories import make_profile, make_user
from tests.helpers import auth


def upload(content: str | bytes, name="dati.csv"):
    data = content.encode("utf-8") if isinstance(content, str) else content
    return {"files": {"file": (name, data, "text/csv")}}


def count(session, model):
    return session.scalar(select(func.count()).select_from(model))


# ======================================================== collaboratori
EMP_URL = "/api/v1/employees/import"
EMP_CSV = "Nome;Cognome;Profilo;Attivo\nMario;Rossi;Senior;sì\nAnna;Bianchi;consultant;no\n"


def _emp_setup(session):
    h = auth(make_user(session, role="admin"))
    make_profile(session, name="Senior")
    make_profile(session, name="Consultant")
    return h


def test_employee_import_defaults_to_preview_and_writes_nothing(api, session):
    h = _emp_setup(session)
    resp = api.post(EMP_URL, headers=h, **upload(EMP_CSV))  # nessun dry_run => anteprima
    assert resp.status_code == 200
    body = resp.json()
    assert body["dry_run"] is True and body["applied"] is False
    assert (body["total_rows"], body["created"], body["updated"], body["unchanged"]) == (2, 2, 0, 0)
    assert count(session, Employee) == 0
    assert "import" not in session.scalars(select(AuditLog.action)).all()


def test_employee_import_confirmation_creates_records(api, session):
    h = _emp_setup(session)
    resp = api.post(f"{EMP_URL}?dry_run=false", headers=h, **upload(EMP_CSV))
    assert resp.status_code == 200 and resp.json()["applied"] is True
    people = {(e.first_name, e.last_name): e for e in session.scalars(select(Employee))}
    assert people[("Mario", "Rossi")].is_active is True
    assert people[("Anna", "Bianchi")].is_active is False
    audit = session.scalar(select(AuditLog).where(AuditLog.action == "import"))
    assert audit.entity_type == "employees" and audit.changes["created"] == 2


def test_employee_import_preview_counts_match_what_confirmation_does(api, session):
    h = _emp_setup(session)
    api.post(f"{EMP_URL}?dry_run=false", headers=h, **upload(EMP_CSV))
    changed = "Nome;Cognome;Profilo;Attivo\nmario;ROSSI;Consultant;sì\nAnna;Bianchi;Consultant;no\nNuovo;Utente;Senior;\n"
    preview = api.post(f"{EMP_URL}?dry_run=true", headers=h, **upload(changed)).json()
    assert (preview["created"], preview["updated"], preview["unchanged"]) == (1, 1, 1)
    assert count(session, Employee) == 2  # l'anteprima non ha scritto
    applied = api.post(f"{EMP_URL}?dry_run=false", headers=h, **upload(changed)).json()
    assert (applied["created"], applied["updated"], applied["unchanged"]) == (1, 1, 1)
    rossi = session.scalar(select(Employee).where(Employee.last_name == "Rossi"))
    assert rossi.default_profile_id == session.scalar(
        select(Profile.id).where(Profile.name == "Consultant")
    )
    assert (
        rossi.first_name == "Mario"
    )  # la corrispondenza ignora le maiuscole ma non altera il nome


def test_employee_import_without_attivo_column_keeps_existing_status(api, session):
    h = _emp_setup(session)
    api.post(f"{EMP_URL}?dry_run=false", headers=h, **upload(EMP_CSV))
    resp = api.post(
        f"{EMP_URL}?dry_run=false",
        headers=h,
        **upload("Nome;Cognome;Profilo\nAnna;Bianchi;Consultant\n"),
    )
    assert resp.json()["unchanged"] == 1
    anna = session.scalar(select(Employee).where(Employee.last_name == "Bianchi"))
    assert anna.is_active is False


def test_employee_import_reports_every_error_by_line(api, session):
    h = _emp_setup(session)
    bad = (
        "Nome;Cognome;Profilo;Attivo\n"
        "Mario;Rossi;Senior;sì\n"  # riga 2: valida
        "Luca;Neri;Inesistente;sì\n"  # riga 3: profilo sconosciuto
        ";Verdi;Senior;sì\n"  # riga 4: nome mancante
        "Mario;Rossi;Senior;sì\n"  # riga 5: duplicato della riga 2
        "Gina;Blu;Senior;forse\n"  # riga 6: valore non valido
    )
    preview = api.post(EMP_URL, headers=h, **upload(bad))
    assert (
        preview.status_code == 200
    )  # in anteprima gli errori sono informazioni, non un fallimento
    body = preview.json()
    assert body["applied"] is False
    assert [e["line"] for e in body["errors"]] == [3, 4, 5, 6]
    assert "Inesistente" in body["errors"][0]["message"]
    assert "riga 2" in body["errors"][2]["message"]


def test_employee_import_is_all_or_nothing(api, session):
    h = _emp_setup(session)
    bad = "Nome;Cognome;Profilo\nMario;Rossi;Senior\nLuca;Neri;Inesistente\n"
    resp = api.post(f"{EMP_URL}?dry_run=false", headers=h, **upload(bad))
    assert resp.status_code == 422
    assert resp.json()["applied"] is False and len(resp.json()["errors"]) == 1
    assert count(session, Employee) == 0  # nemmeno la riga valida è stata importata


def test_employee_import_rejects_inactive_profile_and_bad_files(api, session):
    h = _emp_setup(session)
    make_profile(session, name="Dismesso", is_active=False)
    inactive = api.post(EMP_URL, headers=h, **upload("Nome;Cognome;Profilo\nA;B;Dismesso\n")).json()
    assert "non è attivo" in inactive["errors"][0]["message"]

    missing_col = api.post(EMP_URL, headers=h, **upload("Nome;Cognome\nA;B\n")).json()
    assert (
        missing_col["errors"][0]["line"] is None
        and "mancanti" in missing_col["errors"][0]["message"]
    )
    assert api.post(f"{EMP_URL}?dry_run=false", headers=h, **upload("")).status_code == 422
    assert api.post(EMP_URL, headers=h).status_code == 422  # file assente


def test_employee_import_accepts_excel_variants(api, session):
    h = _emp_setup(session)
    comma_bom = "\ufeffNome,Cognome,Profilo\nMario,Rossi,Senior\n".encode()
    assert api.post(EMP_URL, headers=h, **upload(comma_bom)).json()["created"] == 1
    windows = "Nome;Cognome;Profilo\nRenè;D'Àngelo;Senior\n".encode("cp1252")
    assert api.post(f"{EMP_URL}?dry_run=false", headers=h, **upload(windows)).json()["created"] == 1
    assert (
        session.scalar(select(Employee.first_name).where(Employee.last_name == "D'Àngelo"))
        == "Renè"
    )


# ======================================================== listino
RATES_URL = "/api/v1/profiles/import-rates"
RATES_CSV = (
    "Profilo;Anno;Prezzo giorno;Costo giorno\n"
    "Partner;2026;1.800,00;1.000,00\n"
    "Senior;2026;850;330\n"
    "Senior;2027;900,50;340\n"
)


def test_rates_import_creates_profiles_and_rates_with_italian_numbers(api, session):
    h = auth(make_user(session, role="admin"))
    make_profile(session, name="Senior", sort_order=50)
    body = api.post(f"{RATES_URL}?dry_run=false", headers=h, **upload(RATES_CSV)).json()
    assert body["applied"] is True
    assert (body["created"], body["updated"], body["unchanged"]) == (3, 0, 0)
    assert body["extra"] == {"profili_creati": 1, "profili_aggiornati": 0}

    partner = session.scalar(select(Profile).where(Profile.name == "Partner"))
    assert partner.sort_order == 60  # accodato dopo i profili esistenti
    rate = session.get(ProfileRate, (partner.id, 2026))
    assert (rate.daily_price, rate.daily_cost) == (Decimal("1800.00"), Decimal("1000.00"))
    senior = session.scalar(select(Profile).where(Profile.name == "Senior"))
    assert session.get(ProfileRate, (senior.id, 2027)).daily_price == Decimal("900.50")


def test_rates_import_updates_and_detects_unchanged(api, session):
    h = auth(make_user(session, role="admin"))
    api.post(f"{RATES_URL}?dry_run=false", headers=h, **upload(RATES_CSV))
    again = "Profilo;Anno;Prezzo giorno;Costo giorno\nPartner;2026;1.800,00;1.000,00\nSenior;2026;870;330\n"
    preview = api.post(RATES_URL, headers=h, **upload(again)).json()
    assert (preview["created"], preview["updated"], preview["unchanged"]) == (0, 1, 1)
    assert session.scalar(
        select(ProfileRate.daily_price).where(
            ProfileRate.year == 2026, ProfileRate.daily_cost == 330
        )
    ) == Decimal("850.00")
    applied = api.post(f"{RATES_URL}?dry_run=false", headers=h, **upload(again)).json()
    assert applied["updated"] == 1
    assert session.scalar(
        select(ProfileRate.daily_price).where(
            ProfileRate.year == 2026, ProfileRate.daily_cost == 330
        )
    ) == Decimal("870.00")


def test_rates_import_validation_errors_block_everything(api, session):
    h = auth(make_user(session, role="admin"))
    bad = (
        "Profilo;Anno;Prezzo giorno;Costo giorno\n"
        "Partner;2026;1800;1000\n"  # valida
        "Senior;abcd;850;330\n"  # anno non numerico
        "Senior;1999;850;330\n"  # anno fuori intervallo
        "Senior;2026;-5;330\n"  # negativo
        "Senior;2026;850,123;330\n"  # troppi decimali
        "Partner;2026;1800;1000\n"  # duplicato
        ";2026;1;1\n"  # profilo mancante
    )
    resp = api.post(f"{RATES_URL}?dry_run=false", headers=h, **upload(bad))
    assert resp.status_code == 422
    assert [e["line"] for e in resp.json()["errors"]] == [3, 4, 5, 6, 7, 8]
    assert count(session, Profile) == 0 and count(session, ProfileRate) == 0


# ======================================================== chiusure aziendali
CAL_URL = "/api/v1/calendar/import"


def test_closures_import_formats_defaults_and_existing_days(api, session):
    h = auth(make_user(session, role="admin"))
    session.add(NonWorkingDay(day=date(2026, 12, 25), kind="holiday", description="Natale"))
    session.flush()
    csv_text = "Data;Descrizione\n24/12/2026;Vigilia\n2026-12-25;Natale bis\n31/12/2026;\n"
    body = api.post(f"{CAL_URL}?dry_run=false", headers=h, **upload(csv_text)).json()
    assert (body["created"], body["unchanged"]) == (2, 1)

    days = {d.day: d for d in session.scalars(select(NonWorkingDay))}
    assert days[date(2026, 12, 24)].kind == "company_closure"
    assert days[date(2026, 12, 24)].description == "Vigilia"
    assert days[date(2026, 12, 31)].description == "Chiusura aziendale"  # descrizione di default
    assert days[date(2026, 12, 25)].kind == "holiday"  # la festività esistente non viene toccata


def test_closures_import_errors(api, session):
    h = auth(make_user(session, role="admin"))
    bad = "Data;Descrizione\n24/12/2026;ok\n31/02/2026;impossibile\n24/12/2026;doppia\n"
    resp = api.post(f"{CAL_URL}?dry_run=false", headers=h, **upload(bad))
    assert resp.status_code == 422
    assert [e["line"] for e in resp.json()["errors"]] == [3, 4]
    assert count(session, NonWorkingDay) == 0


def test_closures_import_preview_does_not_write(api, session):
    h = auth(make_user(session, role="admin"))
    body = api.post(CAL_URL, headers=h, **upload("Data\n24/12/2026\n")).json()
    assert body["created"] == 1 and body["applied"] is False
    assert count(session, NonWorkingDay) == 0


def test_rates_import_flags_external_profiles(api, session):
    h = auth(make_user(session, role="admin"))
    csv_text = (
        "Profilo;Anno;Prezzo giorno;Costo giorno;Esterno\n"
        "Subfornitore;2026;700;400;sì\n"  # colonna esplicita
        "Senior;2026;850;330;no\n"
        "Esterni;2026;750;360;\n"  # vuota: vale il nome "Esterni"
    )
    body = api.post(f"{RATES_URL}?dry_run=false", headers=h, **upload(csv_text)).json()
    assert body["applied"] is True and body["extra"]["profili_creati"] == 3
    flags = dict(session.execute(select(Profile.name, Profile.is_external)).all())
    assert flags == {"Subfornitore": True, "Senior": False, "Esterni": True}


def test_rates_import_without_the_column_names_esterni_as_external(api, session):
    h = auth(make_user(session, role="admin"))
    api.post(
        f"{RATES_URL}?dry_run=false",
        headers=h,
        **upload(
            "Profilo;Anno;Prezzo giorno;Costo giorno\nEsterni;2026;750;360\nSenior;2026;850;330\n"
        ),
    )
    flags = dict(session.execute(select(Profile.name, Profile.is_external)).all())
    assert flags == {"Esterni": True, "Senior": False}


def test_rates_import_can_change_the_external_flag_of_an_existing_profile(api, session):
    h = auth(make_user(session, role="admin"))
    make_profile(session, name="Senior")
    csv_text = "Profilo;Anno;Prezzo giorno;Costo giorno;Esterno\nSenior;2026;850;330;sì\n"
    body = api.post(f"{RATES_URL}?dry_run=false", headers=h, **upload(csv_text)).json()
    assert body["extra"] == {"profili_creati": 0, "profili_aggiornati": 1}
    assert session.scalar(select(Profile.is_external).where(Profile.name == "Senior")) is True
    bad = api.post(
        RATES_URL,
        headers=h,
        **upload("Profilo;Anno;Prezzo giorno;Costo giorno;Esterno\nX;2026;1;1;forse\n"),
    )
    assert bad.json()["errors"][0]["line"] == 2
