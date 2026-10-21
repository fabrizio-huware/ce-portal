"""Aiuti per i test delle integrazioni (accesso da programma a programma)."""

from sqlalchemy import update

from app.core.service_auth import ServiceIdentity
from app.models import Integration

EMAIL = "portale-esterno@progetto.iam.gserviceaccount.com"
ALL = ("create", "edit", "read", "export")
BASE = "/api/v1/integrazioni"


def register(api, env, *, name="Portale esterno", email=EMAIL, permissions=ALL) -> dict:
    """L'amministratore registra l'integrazione (e con lei l'utente di servizio)."""
    response = api.post(
        "/api/v1/integrations",
        json={"name": name, "service_account_email": email, "permissions": list(permissions)},
        headers=env.h(env.admin),
    )
    assert response.status_code == 201, response.text
    return response.json()


class Caller:
    """Chiama il contratto come un'integrazione. Di norma azzera il limite di una richiesta al
    secondo prima di ogni chiamata, per non dover aspettare nei test."""

    def __init__(self, api, session, service, *, email=EMAIL, sub="sa-1") -> None:
        self.api, self.session, self.service = api, session, service
        self.email, self.sub = email, sub

    def reset_rate(self) -> None:
        self.session.execute(update(Integration).values(last_used_at=None))
        self.session.commit()

    def request(self, method: str, path: str, *, rate_reset: bool = True, **kwargs):
        if rate_reset:
            self.reset_rate()
        self.service.identity = ServiceIdentity(email=self.email, sub=self.sub, email_verified=True)
        headers = {"Authorization": "Bearer token-di-prova", **kwargs.pop("headers", {})}
        return self.api.request(method, f"{BASE}{path}", headers=headers, **kwargs)

    def get(self, path: str, **kw):
        return self.request("GET", path, **kw)

    def post(self, path: str, **kw):
        return self.request("POST", path, **kw)

    def put(self, path: str, **kw):
        return self.request("PUT", path, **kw)


def new_ce_body(
    env,
    *,
    code="PS-EXT-001-PJT",
    ref="EXT-001",
    requested_by="anna.rossi@huware.com",
    **content_over,
):
    from tests.ce_helpers import simple_content

    content = simple_content(env, 1, **content_over)
    content.pop("expected_revision", None)
    return {"code": code, "external_ref": ref, "requested_by": requested_by, "content": content}


def keys_of(value) -> set[str]:
    """Tutti i nomi di campo presenti in una risposta JSON, a qualunque profondità."""
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in keys_of(v)}
    if isinstance(value, list):
        return {k for v in value for k in keys_of(v)}
    return set()
