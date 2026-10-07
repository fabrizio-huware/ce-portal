# Portale Conti Economici (CE) di progetto

Portale web interno per creare, memorizzare, modificare e ricercare i Conti Economici di progetto:
costi, ricavi, marginalità e impegno delle risorse.

## Stack

| Livello | Tecnologia |
|---|---|
| Backend | Python 3.12, FastAPI (OpenAPI), SQLAlchemy 2, Alembic |
| Frontend | React 18, TypeScript, Vite |
| Database | PostgreSQL (Cloud SQL su GCP) |
| Hosting | Google Cloud Run (ambienti `test` e `prod`) |
| CI/CD | GitHub Actions |

## Struttura

```
backend/    API FastAPI, modello dati, motore di calcolo (app/engine)
frontend/   Interfaccia React (responsive)
infra/      Terraform e Dockerfile (Step 9)
docs/       Analisi funzionale, architettura, guide
.github/    Workflow CI
```

## Avvio in locale

Prerequisiti: Python 3.12, Node 20+, Docker.

```bash
make install     # dipendenze backend e frontend
cp .env.example backend/.env
make db          # PostgreSQL locale (se la porta 5432 è occupata: DB_PORT=5433 make db)
make migrate     # crea lo schema
make seed        # profili, tariffe 2026, festività
make backend     # API su http://localhost:8000  (documentazione: /docs)
```

Per entrare in locale senza Google: imposta in `backend/.env` `BOOTSTRAP_ADMIN_EMAIL=tua.email@huware.com`, riavvia l'API e usa `POST /api/v1/auth/dev-login` da `/docs` (vedi [API](docs/api.md)).

```bash
make frontend    # UI su http://localhost:5173
```

Altri comandi: `make test` (richiede `make db`), `make lint`, `make migration m="..."`.

## Documentazione

- [Analisi funzionale](docs/analisi-funzionale.md)
- [API: autenticazione, permessi, import CSV](docs/api.md)
- [Formule del motore di calcolo](docs/formule.md)
- [Notifiche email (Mailjet)](docs/notifiche.md)
- [Export: Excel, CSV, PDF](docs/export.md)
- [Dashboard: portfolio e carico risorse](docs/dashboard.md)
- [Frontend: grafica, avvio e test](docs/frontend.md)
- [Modello dati](docs/modello-dati.md)
- [Architettura](docs/architettura.md)
- [Convenzioni di sviluppo](CONTRIBUTING.md)

## Stato avanzamento

| Step | Descrizione | Stato |
|---|---|---|
| 1 | Setup repository | completato |
| 2 | Modello dati | completato |
| 3 | Backend base (login Google, utenti, anagrafiche) | completato |
| 4 | Motore di calcolo | completato |
| 5 | API dei CE | completato |
| 6 | Notifiche email | completato |
| 7 | Report ed export | completato |
| 8 | Frontend | in corso: 8a (accesso, elenco, dettaglio), 8b (creazione, modifica, approvazione) e 8c (dashboard) completati |
| 9 | Infrastruttura e deploy | da fare |
| 10 | Test | da fare |
| 11 | Documentazione | da fare |
