"""Carica dati di dimostrazione (fittizi) tramite le API di un backend LOCALE in esecuzione.

    make backend          # in un terminale (con BOOTSTRAP_ADMIN_EMAIL impostata in backend/.env)
    make demo             # in un altro: crea clienti, collaboratori e conti economici di esempio

Entra con l'amministratore iniziale del backend (BOOTSTRAP_ADMIN_EMAIL, letta da backend/.env) oppure con
DEMO_ADMIN_EMAIL. Richiede il login simulato (esiste solo con APP_ENV=local).
Si può rilanciare: ciò che esiste già viene saltato.
"""

import os
import sys
from pathlib import Path

import requests

BASE = os.environ.get("DEMO_API", "http://localhost:8000") + "/api/v1"
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def admin_email() -> str | None:
    """L'amministratore con cui caricare i dati: quello iniziale del backend (BOOTSTRAP_ADMIN_EMAIL)."""
    for name in ("DEMO_ADMIN_EMAIL", "BOOTSTRAP_ADMIN_EMAIL"):
        if os.environ.get(name):
            return os.environ[name].strip()
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "BOOTSTRAP_ADMIN_EMAIL" and value.strip():
                return value.split("#")[0].strip().strip("\"'")
    return None


ADMIN = admin_email()
if not ADMIN:
    sys.exit(
        "Non so con quale amministratore entrare.\n"
        "Imposta BOOTSTRAP_ADMIN_EMAIL in backend/.env, oppure indica l'email: "
        "DEMO_ADMIN_EMAIL=tua.email@huware.com make demo"
    )


def login(email: str) -> dict[str, str]:
    try:
        r = requests.post(f"{BASE}/auth/dev-login", json={"email": email}, timeout=10)
    except requests.ConnectionError:
        sys.exit(
            f"Il backend non risponde su {BASE}. Avvialo con  make backend  in un altro terminale."
        )
    if r.status_code != 200:
        sys.exit(
            f"Login simulato non riuscito per {email}: {r.status_code} {r.text}\n\n"
            "Possibili cause:\n"
            "  1. L'amministratore del tuo database è un'altra email. Indicala così:\n"
            "       DEMO_ADMIN_EMAIL=tua.email@huware.com make demo\n"
            "  2. BOOTSTRAP_ADMIN_EMAIL è stata impostata dopo l'avvio del backend: riavvia  make backend.\n"
            "  3. L'amministratore iniziale si crea solo se il database non ha ancora utenti: se ne esistono già,\n"
            "     usa l'email di un admin esistente (punto 1). Per ripartire da zero cancellando i dati locali:\n"
            "       docker compose down -v && make db && make migrate && make seed\n"
        )
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def post(path: str, headers: dict, body: dict, ok: tuple[int, ...] = (200, 201)):
    r = requests.post(f"{BASE}{path}", headers=headers, json=body, timeout=30)
    if r.status_code in ok:
        return r.json()
    if r.status_code == 409:
        return None  # già presente
    sys.exit(f"{path} -> {r.status_code}: {r.text[:300]}")


admin = login(ADMIN)
USERS = [
    ("anna.presale@huware.com", "Anna Presale", "presale"),
    ("paolo.presale@huware.com", "Paolo Presale", "presale"),
    ("vera.viewer@huware.com", "Vera Viewer", "viewer"),
]
for email, name, role in USERS:
    post("/users", admin, {"email": email, "full_name": name, "role": role})
anna, paolo = login("anna.presale@huware.com"), login("paolo.presale@huware.com")

profiles = {p["name"]: p["id"] for p in requests.get(f"{BASE}/profiles", headers=admin).json()}
if not profiles:
    sys.exit("Listino vuoto: esegui prima  make seed")

clients = {}
for name in ("Alfa Retail", "Beta Banca", "Gamma Energia", "Delta Salute"):
    c = post("/clients", admin, {"name": name})
    clients[name] = (
        c["id"]
        if c
        else next(
            x["id"]
            for x in requests.get(
                f"{BASE}/clients/lookup", headers=admin, params={"q": name}
            ).json()
        )
    )

emps = {}
EMPLOYEES = [
    ("Giulia", "Rossi", "Manager"),
    ("Marco", "Bianchi", "Senior"),
    ("Sara", "Conti", "Senior"),
    ("Luca", "Ferri", "Specialist"),
    ("Elena", "Marino", "Specialist"),
    ("Paolo", "Greco", "Consultant"),
    ("Chiara", "Villa", "Practice"),
]
existing = {
    f"{e['first_name']} {e['last_name']}": e["id"]
    for e in requests.get(f"{BASE}/employees", headers=admin, params={"limit": 200}).json()["items"]
}
for first, last, profile in EMPLOYEES:
    key = f"{first} {last}"
    emps[first] = (
        existing.get(key)
        or post(
            "/employees",
            admin,
            {"first_name": first, "last_name": last, "default_profile_id": profiles[profile]},
        )["id"]
    )


def line(activity, profile, hours, who=None, pm=False, alloc=None):
    body = {"activity": activity, "profile_id": profiles[profile], "is_project_management": pm}
    if hours is not None:
        body["hours"] = str(hours)
    if who:
        body["employee_id"] = emps[who]
    if alloc:
        body["allocations"] = alloc
    return body


def months(start_month: int, end_month: int, pct: str):
    return [{"month": f"2026-{m:02d}-01", "pct": pct} for m in range(start_month, end_month + 1)]


def build(code, client, project, start, end, phases, *, bu=None, sf=None, mode="hours", by=None, state="draft",
          discount="0", signed=None, reason=None, new_version=False):  # fmt: skip
    by = by or anna
    created = post(
        "/ce",
        by,
        {
            "code": code,
            "client_id": clients[client],
            "project_name": project,
            "start_date": start,
            "end_date": end,
            "planning_mode": mode,
            "business_unit": bu,
            "sf_opportunity": sf,
            "max_discount_pct": discount,
            "standard_phases": False,
        },
    )
    if created is None:
        print(f"  = {code} esiste già")
        return
    body = {
        "expected_revision": created["version"]["revision"],
        "header": {
            "client_id": clients[client],
            "project_name": project,
            "start_date": start,
            "end_date": end,
            "planning_mode": mode,
            "business_unit": bu,
            "sf_opportunity": sf,
            "max_discount_pct": discount,
            "signed_price": signed,
        },
        "phases": phases,
    }
    r = requests.put(f"{BASE}/ce/{created['ce']['id']}/content", headers=by, json=body, timeout=30)
    if r.status_code != 200:
        sys.exit(f"{code}: salvataggio {r.status_code} {r.text[:400]}")
    cid = created["ce"]["id"]
    if state in ("submitted", "approved", "rejected"):
        requests.post(f"{BASE}/ce/{cid}/submit", headers=by, timeout=30).raise_for_status()
    if state == "rejected":
        requests.post(
            f"{BASE}/ce/{cid}/reject",
            headers=admin,
            json={"reason": reason or "Da rivedere"},
            timeout=30,
        ).raise_for_status()
    if state == "approved":
        requests.post(f"{BASE}/ce/{cid}/approve", headers=admin, timeout=30).raise_for_status()
    if new_version:
        requests.post(f"{BASE}/ce/{cid}/versions", headers=by, timeout=30).raise_for_status()
    print(f"  + {code} ({state})")
    return cid


print("Conti economici di esempio:")
build(
    "PS-ALFA-ECOM-PJT",
    "Alfa Retail",
    "Piattaforma e-commerce",
    "2026-01-12",
    "2026-06-30",
    [
        {
            "name": "Project Management",
            "lines": [line("Sprint e stand-up", "Manager", 80, "Giulia", pm=True)],
        },
        {
            "name": "Analysis",
            "lines": [
                line("Raccolta requisiti", "Senior", 120, "Marco"),
                line("Disegno soluzione", "Senior", 80, "Sara"),
            ],
        },
        {
            "name": "Delivery",
            "contingency_pct": "10",
            "lines": [
                line("Sviluppo catalogo", "Specialist", 320, "Luca"),
                line("Sviluppo checkout", "Specialist", 240, "Elena"),
                line("Integrazioni di terze parti", "Esterni", 160),
            ],
        },
        {"name": "Testing", "lines": [line("Collaudo funzionale", "Specialist", 80, "Elena")]},
        {"name": "Go-Live", "lines": [line("Rilascio e supporto", "Specialist", 40, "Luca")]},
    ],
    bu="Digital",
    sf="006AL0001",
    state="approved",
    discount="8",
    new_version=True,
)
build(
    "PS-BETA-CRM-PJT",
    "Beta Banca",
    "CRM commerciale",
    "2026-03-02",
    "2026-09-30",
    [
        {
            "name": "Project Management",
            "lines": [line("Coordinamento", "Manager", 60, "Giulia", pm=True)],
        },
        {"name": "Analysis", "lines": [line("Analisi processi", "Senior", 100, "Marco")]},
        {
            "name": "Delivery",
            "lines": [
                line("Configurazione CRM", "Specialist", 400, "Luca"),
                line("Migrazione anagrafiche", "Consultant", 300, "Paolo"),
            ],
        },
        {"name": "Testing", "lines": [line("Test di accettazione", "Senior", 120, "Sara")]},
    ],
    bu="Data",
    sf="006BB0002",
    state="approved",
    by=paolo,
    signed="62000",
)
build(
    "PS-GAMMA-DATA-PJT",
    "Gamma Energia",
    "Data platform",
    "2026-04-01",
    "2026-12-18",
    [
        {
            "name": "Project Management",
            "lines": [line("Coordinamento", "Manager", 90, "Giulia", pm=True)],
        },
        {
            "name": "Delivery",
            "contingency_pct": "5",
            "lines": [
                line("Ingestion dati", "Specialist", 360, "Luca"),
                line("Modello dati", "Practice", 120, "Chiara"),
                line("Cruscotti", "Consultant", 200, "Paolo"),
            ],
        },
    ],
    bu="Data",
    state="submitted",
    by=paolo,
)
build(
    "PS-DELTA-APP-PJT",
    "Delta Salute",
    "App pazienti",
    "2026-05-04",
    "2026-10-30",
    [
        {
            "name": "Allocazione",
            "lines": [
                line(
                    "Coordinamento", "Manager", None, "Giulia", pm=True, alloc=months(5, 10, "20")
                ),
                line("Sviluppo app", "Specialist", None, "Elena", alloc=months(5, 10, "80")),
                line("Sviluppo servizi", "Specialist", None, "Luca", alloc=months(5, 10, "60")),
                line("Esperienza utente", "Senior", None, "Sara", alloc=months(5, 8, "50")),
            ],
        },
    ],
    bu="Digital",
    mode="percent",
    state="draft",
)
build(
    "PS-ALFA-AI-PJT",
    "Alfa Retail",
    "Assistente virtuale",
    "2026-02-02",
    "2026-04-30",
    [
        {
            "name": "Delivery",
            "lines": [
                line("Configurazione assistente", "Specialist", 200, "Elena"),
                line("Addestramento", "Senior", 80, "Marco"),
            ],
        },
    ],
    bu="AI",
    state="rejected",
    reason="Mancano le ore di test e il piano di rilascio.",
)
build(
    "PS-BETA-MIG-PJT",
    "Beta Banca",
    "Migrazione dati",
    "2026-09-01",
    "2026-12-18",
    [
        {
            "name": "Delivery",
            "lines": [
                line("Mappatura sorgenti", "Consultant", 160, "Paolo"),
                line("Caricamento", "Specialist", 240, "Luca"),
            ],
        },
    ],
    bu="Data",
    state="draft",
)
build(
    "PS-GAMMA-BI-PJT",
    "Gamma Energia",
    "Reporting direzionale",
    "2026-02-02",
    "2026-05-29",
    [
        {
            "name": "Delivery",
            "lines": [
                line("Cruscotti direzione", "Consultant", 240, "Paolo"),
                line("Revisione", "Senior", 40, "Marco"),
            ],
        },
    ],
    bu="Data",
    state="approved",
    by=paolo,
)
build(
    "PS-DELTA-SUP-PJT",
    "Delta Salute",
    "Supporto applicativo",
    "2026-06-01",
    "2026-11-30",
    [
        {
            "name": "Project Management",
            "lines": [line("Coordinamento", "Manager", 30, "Giulia", pm=True)],
        },
        {
            "name": "Delivery",
            "lines": [
                line("Assistenza evolutiva", "Specialist", 320, "Elena"),
                line("Assistenza di secondo livello", "Specialist", 160, "Luca"),
            ],
        },
    ],
    bu="Digital",
    state="approved",
)

print("\nFatto. Utenti con cui entrare (accesso simulato):")
print(
    f"  {ADMIN} (admin) · anna.presale@huware.com · paolo.presale@huware.com · vera.viewer@huware.com (viewer)"
)
