"""Strumenti per i test dell'API dei CE: listino, utenti e contenuti pronti all'uso."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.models import Client, NonWorkingDay, Profile, ProfileRate, User
from tests.engine_helpers import FIXTURE
from tests.factories import make_client, make_user
from tests.helpers import auth

PHASE_NAMES = [
    "Project Management",
    "Analysis",
    "Solution Design",
    "Tech Activities",
    "Testing",
    "Training",
    "Documentation",
    "Go-Live",
    "Stability Period",
]


@dataclass
class Env:
    admin: User
    presale: User
    other: User  # un secondo presale (non autore dei CE di `presale`)
    viewer: User
    client: Client
    profiles: dict[str, Profile]
    headers: dict[str, dict[str, str]] = field(default_factory=dict)

    def h(self, user: User) -> dict[str, str]:
        return auth(user)


def seed_listino(session, year: int = 2026) -> dict[str, Profile]:
    """Il listino del foglio reale (inclusi Partner ed Esterni) per l'anno indicato."""
    profiles = {}
    for order, (name, rate) in enumerate(FIXTURE["rates"].items(), start=1):
        profile = Profile(name=name, sort_order=order * 10, is_external=(name == "Esterni"))
        session.add(profile)
        session.flush()
        session.add(
            ProfileRate(
                profile_id=profile.id,
                year=year,
                daily_price=Decimal(rate["daily_price"]),
                daily_cost=Decimal(rate["daily_cost"]),
            )
        )
        profiles[name] = profile
    session.flush()
    return profiles


def make_env(session) -> Env:
    return Env(
        admin=make_user(session, role="admin"),
        presale=make_user(session, role="presale"),
        other=make_user(session, role="presale"),
        viewer=make_user(session, role="viewer"),
        client=make_client(session, name="Cliente di prova"),
        profiles=seed_listino(session),
    )


def add_closures(session, *days: date) -> None:
    for day in days:
        session.add(NonWorkingDay(day=day, kind="holiday", description="Festivo di prova"))
    session.flush()


# ------------------------------------------------------------------ contenuti
def header(env: Env, **over) -> dict:
    values = {
        "client_id": str(env.client.id),
        "project_name": "Progetto di prova",
        "start_date": "2026-01-20",
        "end_date": "2026-04-20",
        "planning_mode": "hours",
    }
    values.update(over)
    return values


def create_body(env: Env, code="PS-TEST-AI-PJT", **over) -> dict:
    return {"code": code, **header(env), **over}


def real_ce_content(env: Env, revision: int, **header_over) -> dict:
    """Il CE reale (468 ore, 9 fasi) in formato API: ricavi 47.162,50, costi 20.200,00."""
    phases = []
    for phase in FIXTURE["phases"]:
        lines = [
            {
                "activity": task["name"] or f"{phase['code']}-{task['id']}",
                "profile_id": str(env.profiles[profile].id),
                "hours": hours,
                "is_project_management": phase["code"] == "PM",
            }
            for task in phase["tasks"]
            for profile, hours in task["hours"].items()
        ]
        phases.append({"name": phase["code"], "contingency_pct": "0", "lines": lines})
    return {
        "expected_revision": revision,
        "header": header(env, **header_over),
        "non_working_days": [{"month": "2026-01-01", "non_working_days": 5}],
        "phases": phases,
        "milestones": [{"month": "2026-04-01", "label": "GoLive"}],
    }


def percent_ce_content(env: Env, revision: int) -> dict:
    """La griglia % dello scenario B (gen-apr 2026)."""
    sc = FIXTURE["scenarios"]["B"]
    months = ["2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01"]
    lines = [
        {
            "activity": row["profile"],
            "profile_id": str(env.profiles[row["profile"]].id),
            "allocations": [
                {"month": m, "pct": p} for m, p in zip(months, row["pct"], strict=True)
            ],
        }
        for row in sc["rows"]
    ]
    return {
        "expected_revision": revision,
        "header": header(env, planning_mode="percent"),
        "non_working_days": [{"month": "2026-01-01", "non_working_days": 5}],
        "phases": [{"name": "Allocazione", "contingency_pct": "0", "lines": lines}],
        "milestones": [],
    }


def simple_content(env: Env, revision: int, hours="16", profile="Senior", **header_over) -> dict:
    return {
        "expected_revision": revision,
        "header": header(env, **header_over),
        "phases": [
            {
                "name": "Fase",
                "lines": [
                    {
                        "activity": "Attività",
                        "profile_id": str(env.profiles[profile].id),
                        "hours": hours,
                    }
                ],
            }
        ],
    }


# ------------------------------------------------------------------ chiamate
def create(api, env: Env, user=None, code="PS-TEST-AI-PJT", **over) -> dict:
    resp = api.post(
        "/api/v1/ce", headers=env.h(user or env.presale), json=create_body(env, code, **over)
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def save(api, env: Env, ce_id: str, content: dict, user=None):
    return api.put(f"/api/v1/ce/{ce_id}/content", headers=env.h(user or env.presale), json=content)


def create_filled(api, env: Env, code="PS-TEST-AI-PJT", user=None, content=None) -> dict:
    """CE creato e già compilato con una riga semplice (16 ore di Senior: 1.700 € di ricavi)."""
    created = create(api, env, user, code)
    body = content or simple_content(env, created["version"]["revision"])
    body["expected_revision"] = created["version"]["revision"]
    resp = save(api, env, created["ce"]["id"], body, user)
    assert resp.status_code == 200, resp.text
    return resp.json()


def approved_ce(api, env: Env, code="PS-TEST-AI-PJT", content=None) -> dict:
    ce = create_filled(api, env, code, content=content)
    resp = api.post(f"/api/v1/ce/{ce['ce']['id']}/approve", headers=env.h(env.admin))
    assert resp.status_code == 200, resp.text
    return resp.json()
