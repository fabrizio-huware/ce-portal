"""Workflow dei CE: ogni azione, in ogni stato, con ogni tipo di utente."""

import pytest
from sqlalchemy import select

from app.models import CEVersion
from tests.ce_helpers import create, create_filled, simple_content

URL = "/api/v1/ce"


# ------------------------------------------------------------------ portare un CE in uno stato
def put_in_state(api, env, state: str, code="PS-WF-1") -> str:
    ce = create_filled(api, env, code)
    ce_id = ce["ce"]["id"]
    owner, admin = env.h(env.presale), env.h(env.admin)
    if state in ("submitted", "rejected", "approved"):
        assert api.post(f"{URL}/{ce_id}/submit", headers=owner).status_code == 200
    if state == "rejected":
        assert (
            api.post(
                f"{URL}/{ce_id}/reject", headers=admin, json={"reason": "Mancano le ore di test"}
            ).status_code
            == 200
        )
    if state == "approved":
        assert api.post(f"{URL}/{ce_id}/approve", headers=admin).status_code == 200
    return ce_id


def act(api, env, ce_id: str, action: str, who: str):
    user = {"owner": env.presale, "other": env.other, "admin": env.admin, "viewer": env.viewer}[who]
    headers = env.h(user)
    if action == "edit":
        current = api.get(f"{URL}/{ce_id}", headers=env.h(env.admin)).json()
        return api.put(
            f"{URL}/{ce_id}/content",
            headers=headers,
            json=simple_content(env, current["version"]["revision"], hours="24"),
        )
    if action == "reject":
        return api.post(
            f"{URL}/{ce_id}/reject", headers=headers, json={"reason": "Motivo del rifiuto"}
        )
    if action == "discard":
        return api.delete(f"{URL}/{ce_id}/open-version", headers=headers)
    if action == "new_version":
        return api.post(f"{URL}/{ce_id}/versions", headers=headers)
    return api.post(f"{URL}/{ce_id}/{action}", headers=headers)


# (stato, azione, chi) -> codice atteso
CASES = [
    # --- bozza
    ("draft", "edit", "owner", 200),
    ("draft", "edit", "admin", 200),
    ("draft", "edit", "other", 403),
    ("draft", "edit", "viewer", 403),
    ("draft", "submit", "owner", 200),
    ("draft", "submit", "admin", 200),
    ("draft", "submit", "other", 403),
    ("draft", "submit", "viewer", 403),
    ("draft", "withdraw", "owner", 409),
    ("draft", "withdraw", "other", 403),
    ("draft", "approve", "admin", 200),  # l'admin approva SEMPRE, anche da bozza
    ("draft", "approve", "owner", 403),
    ("draft", "approve", "other", 403),
    ("draft", "approve", "viewer", 403),
    ("draft", "reject", "admin", 409),
    ("draft", "reject", "owner", 403),
    ("draft", "new_version", "owner", 409),
    ("draft", "new_version", "other", 403),
    ("draft", "discard", "owner", 409),  # è la prima versione
    # --- in approvazione
    ("submitted", "edit", "owner", 409),  # bloccato per il presale
    ("submitted", "edit", "admin", 200),  # l'admin può comunque intervenire
    ("submitted", "edit", "other", 403),
    ("submitted", "submit", "owner", 409),
    ("submitted", "withdraw", "owner", 200),
    ("submitted", "withdraw", "admin", 200),
    ("submitted", "withdraw", "other", 403),
    ("submitted", "withdraw", "viewer", 403),
    ("submitted", "approve", "admin", 200),
    ("submitted", "approve", "owner", 403),
    ("submitted", "reject", "admin", 200),
    ("submitted", "reject", "owner", 403),
    ("submitted", "reject", "other", 403),
    ("submitted", "new_version", "owner", 409),
    # --- rifiutato
    ("rejected", "edit", "owner", 200),
    ("rejected", "edit", "admin", 200),
    ("rejected", "edit", "other", 403),
    ("rejected", "submit", "owner", 200),
    ("rejected", "submit", "other", 403),
    ("rejected", "withdraw", "owner", 409),
    ("rejected", "approve", "admin", 200),  # anche da rifiutato
    ("rejected", "reject", "admin", 409),
    ("rejected", "new_version", "owner", 409),
    # --- approvato
    ("approved", "edit", "owner", 409),
    ("approved", "edit", "admin", 409),
    ("approved", "edit", "other", 403),
    ("approved", "submit", "owner", 409),
    ("approved", "withdraw", "owner", 409),
    ("approved", "approve", "admin", 409),
    ("approved", "reject", "admin", 409),
    ("approved", "discard", "owner", 409),
    ("approved", "new_version", "owner", 201),
    ("approved", "new_version", "admin", 201),
    ("approved", "new_version", "other", 403),
    ("approved", "new_version", "viewer", 403),
]


@pytest.mark.parametrize(
    "state,action,who,expected", CASES, ids=[f"{s}-{a}-{w}" for s, a, w, _ in CASES]
)
def test_state_machine(api, env, state, action, who, expected):
    ce_id = put_in_state(api, env, state)
    resp = act(api, env, ce_id, action, who)
    assert resp.status_code == expected, resp.text


# ------------------------------------------------------------------ effetti delle transizioni
def test_full_lifecycle_and_history(api, env, session):
    ce = create_filled(api, env, "PS-LIFE-1")
    ce_id = ce["ce"]["id"]
    owner, admin = env.h(env.presale), env.h(env.admin)

    submitted = api.post(f"{URL}/{ce_id}/submit", headers=owner).json()
    assert submitted["version"]["status"] == "submitted" and submitted["version"]["submitted_at"]

    rejected = api.post(
        f"{URL}/{ce_id}/reject", headers=admin, json={"reason": "Servono più ore di test"}
    ).json()
    v = rejected["version"]
    assert v["status"] == "rejected" and v["rejection_reason"] == "Servono più ore di test"
    assert v["rejected_by"]["id"] == str(env.admin.id) and v["rejected_at"]

    # l'autore corregge (resta "rifiutato" finché non reinvia) e reinvia
    current = api.get(f"{URL}/{ce_id}", headers=owner).json()
    edited = api.put(
        f"{URL}/{ce_id}/content",
        headers=owner,
        json=simple_content(env, current["version"]["revision"], hours="40"),
    ).json()
    assert edited["version"]["status"] == "rejected"
    resubmitted = api.post(f"{URL}/{ce_id}/submit", headers=owner).json()
    assert resubmitted["version"]["status"] == "submitted"
    assert (
        resubmitted["version"]["rejected_by"] is None
        and resubmitted["version"]["rejection_reason"] is None
    )

    approved = api.post(f"{URL}/{ce_id}/approve", headers=admin).json()
    assert approved["version"]["status"] == "approved"
    assert approved["version"]["approved_by"]["id"] == str(env.admin.id)

    history = api.get(f"{URL}/{ce_id}/history", headers=owner).json()
    assert [h["action"] for h in history] == [
        "approve",
        "submit",
        "save",
        "reject",
        "submit",
        "save",
        "create",
    ]
    assert history[0]["user"]["id"] == str(env.admin.id) and history[-1]["user"]["id"] == str(
        env.presale.id
    )
    assert history[3]["changes"]["reason"] == "Servono più ore di test"


def test_approval_freezes_the_totals(api, env, session):
    ce = create_filled(api, env, "PS-FREEZE-1")
    ce_id = ce["ce"]["id"]
    api.post(f"{URL}/{ce_id}/approve", headers=env.h(env.admin))
    version = session.scalars(select(CEVersion)).one()
    totals = version.approved_totals
    assert (totals["revenue"], totals["cost"], totals["margin"]) == ("1700.00", "660.00", "1040.00")
    assert totals["days_total"] == "2.00000" and totals["days_delivery"] == "2.00000"
    assert totals["days_project_management"] == "0.00000"
    assert totals["phases"] == [{"name": "Fase", "revenue": "1700.00"}]
    assert version.approved_by == env.admin.id and version.approved_at is not None
    assert version.status == "approved"


def test_empty_ces_cannot_be_submitted_or_approved(api, env):
    created = create(api, env)  # 9 fasi vuote
    ce_id = created["ce"]["id"]
    submit = api.post(f"{URL}/{ce_id}/submit", headers=env.h(env.presale))
    approve = api.post(f"{URL}/{ce_id}/approve", headers=env.h(env.admin))
    assert submit.status_code == 422 and approve.status_code == 422
    assert "non contiene ore" in submit.json()["detail"]["issues"][0]
    assert (
        api.get(f"{URL}/{ce_id}", headers=env.h(env.presale)).json()["version"]["status"] == "draft"
    )


def test_reject_requires_a_reason(api, env):
    ce_id = put_in_state(api, env, "submitted")
    url = f"{URL}/{ce_id}/reject"
    assert api.post(url, headers=env.h(env.admin), json={}).status_code == 422
    assert api.post(url, headers=env.h(env.admin), json={"reason": "  "}).status_code == 422


def test_withdraw_returns_the_ce_to_draft_and_unlocks_editing(api, env):
    ce_id = put_in_state(api, env, "submitted")
    back = api.post(f"{URL}/{ce_id}/withdraw", headers=env.h(env.presale)).json()
    assert back["version"]["status"] == "draft" and back["version"]["submitted_at"] is None
    assert act(api, env, ce_id, "edit", "owner").status_code == 200


def test_every_transition_changes_the_revision(api, env):
    ce_id = put_in_state(api, env, "draft")
    revisions = []
    for action, who in (
        ("submit", "owner"),
        ("withdraw", "owner"),
        ("submit", "owner"),
        ("approve", "admin"),
    ):
        resp = act(api, env, ce_id, action, who)
        revisions.append(resp.json()["version"]["revision"])
    assert revisions == sorted(set(revisions))  # crescente e senza ripetizioni


def test_stale_screens_cannot_save_after_a_state_change(api, env):
    ce = create_filled(api, env, "PS-STALE-1")
    ce_id = ce["ce"]["id"]
    seen = ce["version"]["revision"]
    api.post(f"{URL}/{ce_id}/submit", headers=env.h(env.presale))
    api.post(f"{URL}/{ce_id}/withdraw", headers=env.h(env.presale))
    resp = api.put(
        f"{URL}/{ce_id}/content",
        headers=env.h(env.presale),
        json=simple_content(env, seen, hours="99"),
    )
    assert resp.status_code == 409 and "current_revision" in resp.json()["detail"]


# ------------------------------------------------------------------ pulsanti dell'interfaccia
ALL = (
    "edit",
    "submit",
    "withdraw",
    "approve",
    "reject",
    "new_version",
    "discard_version",
    "realign",
    "delete",
)
ALLOWED = {
    ("draft", "presale-owner"): {"edit", "submit"},
    ("draft", "presale-other"): set(),
    ("draft", "admin"): {"edit", "submit", "approve", "realign", "delete"},
    ("submitted", "presale-owner"): {"withdraw"},
    ("submitted", "admin"): {"edit", "withdraw", "approve", "reject", "realign", "delete"},
    ("rejected", "presale-owner"): {"edit", "submit"},
    ("rejected", "admin"): {"edit", "submit", "approve", "realign", "delete"},
    ("approved", "presale-owner"): {"new_version"},
    ("approved", "presale-other"): set(),
    ("approved", "admin"): {"new_version", "delete"},
}


@pytest.mark.parametrize("state,who", list(ALLOWED), ids=[f"{s}-{w}" for s, w in ALLOWED])
def test_actions_flags_match_what_the_user_can_do(api, env, state, who):
    ce_id = put_in_state(api, env, state)
    user = {"presale-owner": env.presale, "presale-other": env.other, "admin": env.admin}[who]
    actions = api.get(f"{URL}/{ce_id}", headers=env.h(user)).json()["actions"]
    assert {name for name in ALL if actions[name]} == ALLOWED[(state, who)]


def test_deleted_ces_refuse_every_action(api, env):
    ce_id = put_in_state(api, env, "draft")
    assert api.delete(f"{URL}/{ce_id}", headers=env.h(env.admin)).status_code == 204
    for action in ("submit", "withdraw", "approve"):
        assert act(api, env, ce_id, action, "admin").status_code == 404, action
    put = api.put(f"{URL}/{ce_id}/content", headers=env.h(env.admin), json=simple_content(env, 1))
    assert put.status_code == 404
    assert api.get(f"{URL}/{ce_id}", headers=env.h(env.admin)).status_code == 404
