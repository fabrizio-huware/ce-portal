"""Esito della trattativa («Close Won» / «Close Lost») sui CE approvati."""

import uuid
from io import BytesIO

import pytest
from pypdf import PdfReader
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.models import CE, AuditLog
from tests.ce_helpers import approved_ce, create_filled
from tests.factories import make_business_unit, make_user
from tests.test_ce_visibility import _switch

URL = "/api/v1/ce"


def _put(api, env, ce, outcome, note=None, user=None):
    body = {"outcome": outcome, **({"note": note} if note is not None else {})}
    return api.put(f"{URL}/{ce}/outcome", headers=env.h(user or env.presale), json=body)


def _detail(api, env, ce, user=None):
    return api.get(f"{URL}/{ce}", headers=env.h(user or env.admin)).json()


def _manager(session, env, unit=None):
    return make_user(session, role="bu_manager", business_unit_id=(unit or env.unit).id)


def _pdf(resp) -> str:
    return "\n".join(p.extract_text() for p in PdfReader(BytesIO(resp.content)).pages)


# ------------------------------------------------------------------ quando si può
def test_the_outcome_needs_an_approved_latest_version(api, env):
    draft = create_filled(api, env, code="PS-OUT-1-PJT")["ce"]["id"]
    refused = _put(api, env, draft, "won")
    assert refused.status_code == 409 and "approvata" in refused.json()["detail"]
    assert _detail(api, env, draft)["actions"]["set_outcome"] is False
    ce = approved_ce(api, env, code="PS-OUT-2-PJT")["ce"]["id"]
    assert _detail(api, env, ce)["actions"]["set_outcome"] is True
    done = _put(api, env, ce, "won", "Firmato il contratto quadro")
    assert done.status_code == 200
    out = done.json()["outcome"]
    assert (out["value"], out["note"], out["by"]["full_name"]) == (
        "won",
        "Firmato il contratto quadro",
        env.presale.full_name,
    )
    assert out["at"]


def test_the_outcome_changes_only_while_the_latest_version_is_approved(api, env):
    ce = approved_ce(api, env, code="PS-OUT-3-PJT")["ce"]["id"]
    assert _put(api, env, ce, "won").status_code == 200
    assert (
        api.post(f"{URL}/{ce}/versions", headers=env.h(env.presale)).status_code == 201
    )  # dopo Close Won: varianti
    assert _detail(api, env, ce)["outcome"]["value"] == "won"  # l'esito resta finché non cambia
    blocked = _put(api, env, ce, "lost")
    assert blocked.status_code == 409 and _detail(api, env, ce)["actions"]["set_outcome"] is False


# ------------------------------------------------------------------ chi può
def test_admin_involved_manager_and_author_can_the_others_cannot(api, env, session):
    ce = approved_ce(api, env, code="PS-OUT-4-PJT")["ce"]["id"]
    involved = _manager(session, env)  # la business unit del CE
    elsewhere = _manager(session, env, unit=make_business_unit(session, name="Altrove"))
    session.commit()
    assert _put(api, env, ce, "won", user=env.other).status_code == 403  # un altro presale
    assert (
        _put(api, env, ce, "won", user=elsewhere).status_code == 403
    )  # responsabile di un'altra business unit
    assert _put(api, env, ce, "won", user=env.viewer).status_code == 403
    assert _detail(api, env, ce, user=elsewhere)["actions"]["set_outcome"] is False
    for who in (involved, env.admin, env.presale):  # coinvolto, admin, autore
        assert _detail(api, env, ce, user=who)["actions"]["set_outcome"] is True
        assert _put(api, env, ce, "lost", user=who).status_code == 200
        assert _put(api, env, ce, None, user=who).status_code == 200  # e la tolgono


def test_with_visibility_on_a_ce_not_seen_is_not_found(api, env, session):
    ce = approved_ce(api, env, code="PS-OUT-5-PJT")["ce"]["id"]
    elsewhere = make_user(session, role="presale")
    session.commit()
    _switch(api, env, True)
    assert (
        _put(api, env, ce, "won", user=elsewhere).status_code == 404
    )  # non lo vede: nemmeno la rotta dell'esito


# ------------------------------------------------------------------ cambiare, togliere, registrare
def test_change_remove_and_the_history(api, env, session):
    ce = approved_ce(api, env, code="PS-OUT-6-PJT")["ce"]["id"]
    assert _put(api, env, ce, "won").status_code == 200
    assert _put(api, env, ce, "lost", "Ha scelto un concorrente", user=env.admin).status_code == 200
    assert (
        _put(api, env, ce, "lost", "Ha scelto un concorrente", user=env.admin).status_code == 200
    )  # uguale: nulla da fare
    assert (
        _put(api, env, ce, "lost", "Prezzo troppo alto", user=env.admin).status_code == 200
    )  # solo la nota
    removed = _put(api, env, ce, None)
    assert removed.status_code == 200 and removed.json()["outcome"] is None
    assert (
        _put(api, env, ce, None, note="una nota").status_code == 422
    )  # la nota serve solo con un esito
    session.expire_all()
    changes = [
        e.changes
        for e in session.scalars(
            select(AuditLog)
            .where(AuditLog.entity_id == uuid.UUID(ce), AuditLog.action == "set_outcome")
            .order_by(AuditLog.id)
        )
    ]
    assert changes == [
        {"from": None, "to": "won", "note": None},
        {"from": "won", "to": "lost", "note": "Ha scelto un concorrente"},
        {"from": "lost", "to": "lost", "note": "Prezzo troppo alto"},
        {"from": "lost", "to": None, "note": None},
    ]


# ------------------------------------------------------------------ nuova versione ed eliminazione
def test_close_lost_blocks_new_versions_close_won_does_not(api, env):
    ce = approved_ce(api, env, code="PS-OUT-7-PJT")["ce"]["id"]
    _put(api, env, ce, "lost")
    detail = _detail(api, env, ce, user=env.presale)
    assert detail["actions"]["new_version"] is False
    blocked = api.post(f"{URL}/{ce}/versions", headers=env.h(env.presale))
    assert blocked.status_code == 409 and "Close Lost" in blocked.json()["detail"]
    _put(api, env, ce, None)
    assert _detail(api, env, ce, user=env.presale)["actions"]["new_version"] is True
    _put(api, env, ce, "won")
    assert api.post(f"{URL}/{ce}/versions", headers=env.h(env.presale)).status_code == 201


@pytest.mark.parametrize("outcome,label", [("won", "Close Won"), ("lost", "Close Lost")])
def test_a_ce_with_an_outcome_cannot_be_deleted_and_says_why(api, env, outcome, label):
    ce = approved_ce(api, env, code=f"PS-OUT-8-{outcome}-PJT")["ce"]["id"]
    _put(api, env, ce, outcome)
    actions = _detail(api, env, ce)["actions"]
    assert (
        actions["delete"] is False and label in actions["delete_blocked_reason"]
    )  # la segnalazione
    refused = api.delete(f"{URL}/{ce}", headers=env.h(env.admin))
    assert (
        refused.status_code == 409
        and label in refused.json()["detail"]
        and "toglilo" in refused.json()["detail"]
    )
    _put(api, env, ce, None)
    after = _detail(api, env, ce)["actions"]
    assert after["delete"] is True and after["delete_blocked_reason"] is None
    assert api.delete(f"{URL}/{ce}", headers=env.h(env.admin)).status_code == 204


# ------------------------------------------------------------------ elenco, viewer, integrazioni, PDF
def test_the_list_shows_and_filters_the_outcome(api, env):
    won = approved_ce(api, env, code="PS-OUT-9-PJT")["ce"]["id"]
    lost = approved_ce(api, env, code="PS-OUT-10-PJT")["ce"]["id"]
    approved_ce(api, env, code="PS-OUT-11-PJT")  # senza esito
    _put(api, env, won, "won")
    _put(api, env, lost, "lost")
    h = env.h(env.admin)

    def listed(value):
        resp = api.get(f"{URL}?limit=200&code=PS-OUT-&outcome={value}", headers=h)
        assert resp.status_code == 200
        return {i["code"]: i["outcome"] for i in resp.json()["items"]}

    assert listed("won") == {"PS-OUT-9-PJT": "won"}
    assert listed("lost") == {"PS-OUT-10-PJT": "lost"}
    assert listed("none") == {"PS-OUT-11-PJT": None}
    everything = api.get(f"{URL}?limit=200&code=PS-OUT-", headers=h).json()["items"]
    assert {i["code"]: i["outcome"] for i in everything} == {
        "PS-OUT-9-PJT": "won",
        "PS-OUT-10-PJT": "lost",
        "PS-OUT-11-PJT": None,
    }
    assert api.get(f"{URL}?outcome=boh", headers=h).status_code == 422
    export = api.get(f"{URL}/export?format=csv&code=PS-OUT-&outcome=lost", headers=h)
    assert export.status_code == 200 and "PS-OUT-10-PJT" in export.text
    assert "PS-OUT-11-PJT" not in export.text and "PS-OUT-9-PJT" not in export.text


def test_the_viewer_sees_the_outcome_but_never_the_note(api, env):
    ce = approved_ce(api, env, code="PS-OUT-12-PJT")["ce"]["id"]
    _put(api, env, ce, "lost", "Segreto commerciale del motivo")
    h = env.h(env.viewer)
    listed = api.get(f"{URL}/summaries?limit=200", headers=h).json()["items"]
    assert [i["outcome"] for i in listed if i["code"] == "PS-OUT-12-PJT"] == ["lost"]
    one = api.get(f"{URL}/summaries/{ce}", headers=h)
    assert one.json()["outcome"] == "lost"
    assert "Segreto" not in one.text and "note" not in one.json()
    assert "Segreto" not in api.get(f"{URL}/summaries?limit=200", headers=h).text


def test_the_pdfs_show_the_outcome(api, env):
    ce = approved_ce(api, env, code="PS-OUT-13-PJT")["ce"]["id"]
    plain = api.get(f"{URL}/{ce}/export?format=pdf&variant=full", headers=env.h(env.admin))
    assert "Esito" not in _pdf(plain)
    _put(api, env, ce, "won", "Nota riservata")
    full = _pdf(api.get(f"{URL}/{ce}/export?format=pdf&variant=full", headers=env.h(env.admin)))
    assert "Esito" in full and "Close Won" in full
    summary = _pdf(
        api.get(f"{URL}/{ce}/export?format=pdf&variant=summary", headers=env.h(env.admin))
    )
    assert "Esito" in summary and "Close Won" in summary and "Nota riservata" not in summary
    viewer = _pdf(api.get(f"{URL}/summaries/{ce}/export?format=pdf", headers=env.h(env.viewer)))
    assert "Close Won" in viewer and "Nota riservata" not in viewer


# ------------------------------------------------------------------ database
def test_the_database_refuses_a_half_outcome(session, env):
    session.commit()  # gli utenti di prova devono esistere anche dopo i rollback degli inserimenti rifiutati
    with pytest.raises(IntegrityError):  # il valore senza data e autore
        session.execute(
            text("INSERT INTO ce (code, created_by, outcome) VALUES ('X-1', :u, 'won')"),
            {"u": env.presale.id},
        )
    session.rollback()
    with pytest.raises(IntegrityError):  # un valore che non esiste
        session.execute(
            text(
                "INSERT INTO ce (code, created_by, outcome, outcome_at, outcome_by) VALUES ('X-2', :u, 'forse', now(), :u)"
            ),
            {"u": env.presale.id},
        )
    session.rollback()
    with pytest.raises(IntegrityError):  # una nota senza esito
        session.execute(
            text("INSERT INTO ce (code, created_by, outcome_note) VALUES ('X-3', :u, 'nota')"),
            {"u": env.presale.id},
        )
    session.rollback()
    session.execute(
        text(
            "INSERT INTO ce (code, created_by, outcome, outcome_at, outcome_by) VALUES ('X-4', :u, 'lost', now(), :u)"
        ),
        {"u": env.presale.id},
    )  # e un esito completo sì
    assert session.scalar(select(CE.outcome).where(CE.code == "X-4")) == "lost"
