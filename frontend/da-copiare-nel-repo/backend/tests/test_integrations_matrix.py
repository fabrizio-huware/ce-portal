"""Matrice dei permessi del contratto per i programmi esterni.

Come per le persone: ogni rotta è provata senza token, con il token di una persona (che non vale) e con
integrazioni che hanno o non hanno il permesso giusto. Il test finale fallisce se esiste una rotta non
elencata: una rotta nuova non può essere dimenticata senza una decisione esplicita sul permesso.
"""

import pytest

from tests.s2s_helpers import ALL, BASE, Caller, register

ID = "00000000-0000-0000-0000-000000000000"
CONTRACT = [  # (metodo, percorso, parametri, permesso necessario)
    ("GET", "/anagrafiche/clienti", {}, "read"),
    ("GET", "/anagrafiche/business-unit", {}, "read"),
    ("GET", "/anagrafiche/profili", {}, "read"),
    ("GET", "/anagrafiche/collaboratori", {}, "read"),
    ("GET", "/ce", {}, "read"),
    ("POST", "/ce", {"json": {}}, "create"),
    ("GET", f"/ce/{ID}", {}, "read"),
    ("GET", f"/ce/{ID}/content", {}, "read"),
    ("PUT", f"/ce/{ID}/content", {"json": {}}, "edit"),
    ("GET", f"/ce/{ID}/pdf", {}, "export"),
]
IDS = [f"{m} {p} ({perm})" for m, p, _, perm in CONTRACT]
OTHER = "secondo@p.iam.gserviceaccount.com"


@pytest.mark.parametrize("method,path,kwargs,permission", CONTRACT, ids=IDS)
def test_without_a_token_nothing_is_allowed(
    api, env, session, service, method, path, kwargs, permission
):
    register(api, env)
    assert api.request(method, f"{BASE}{path}", **kwargs).status_code == 401


@pytest.mark.parametrize("method,path,kwargs,permission", CONTRACT, ids=IDS)
def test_a_persons_portal_token_never_opens_the_contract(
    api, env, session, service, method, path, kwargs, permission
):
    register(api, env)
    service.fail = True  # un token del portale non è un token Google: la verifica lo rifiuta
    for user in (env.admin, env.presale, env.viewer):
        response = api.request(method, f"{BASE}{path}", headers=env.h(user), **kwargs)
        assert response.status_code == 401, user.role


@pytest.mark.parametrize("method,path,kwargs,permission", CONTRACT, ids=IDS)
def test_the_right_permission_is_required_and_enough(
    api, env, session, service, method, path, kwargs, permission
):
    register(api, env, permissions=[p for p in ALL if p != permission])
    register(api, env, name="Solo questo", email=OTHER, permissions=[permission])
    without = Caller(api, session, service)
    only = Caller(api, session, service, email=OTHER, sub="sa-2")
    assert without.request(method, path, **kwargs).status_code == 403
    response = only.request(method, path, **kwargs)
    assert response.status_code not in (401, 403, 429) and response.status_code < 500, response.text


@pytest.mark.parametrize("method,path,kwargs,permission", CONTRACT, ids=IDS)
def test_an_unregistered_account_is_refused_everywhere(
    api, env, session, service, method, path, kwargs, permission
):
    register(api, env)
    stranger = Caller(api, session, service, email="sconosciuto@p.iam.gserviceaccount.com", sub="x")
    assert stranger.request(method, path, **kwargs).status_code == 401


def test_every_contract_route_is_in_the_matrix(app):
    """Una rotta nuova sotto /api/v1/integrazioni senza una riga qui fa fallire questo test."""
    actual = {
        (method.upper(), path.removeprefix(BASE).replace("{ce_id}", ID))
        for path, operations in app.openapi()["paths"].items()
        if path.startswith(f"{BASE}/")
        for method in operations
        if method in {"get", "post", "put", "patch", "delete"}
    }
    covered = {(m, p) for m, p, _, _ in CONTRACT}
    assert actual - covered == set(), "rotta del contratto senza regola di permesso"
    assert covered - actual == set(), "righe della matrice per rotte che non esistono più"
