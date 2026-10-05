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
backend/    API FastAPI, modello dati, motore di calcolo
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
make db          # PostgreSQL locale (crea anche il database di test)
make migrate     # crea lo schema
make seed        # profili, tariffe 2026, festività
make backend     # API su http://localhost:8000  (documentazione: /docs)
make frontend    # UI su http://localhost:5173
```

Altri comandi: `make test` (richiede `make db`), `make lint`, `make migration m="..."`.

## Documentazione

- [Analisi funzionale](docs/analisi-funzionale.md)
- [Modello dati](docs/modello-dati.md)
- [Architettura](docs/architettura.md)
- [Convenzioni di sviluppo](CONTRIBUTING.md)

## Stato avanzamento

| Step | Descrizione | Stato |
|---|---|---|
| 1 | Setup repository | completato |
| 2 | Modello dati | completato |
| 3 | Backend base (login Google, utenti, anagrafiche) | da fare |
| 4 | Motore di calcolo | da fare |
| 5 | API dei CE | da fare |
| 6 | Notifiche email | da fare |
| 7 | Report ed export | da fare |
| 8 | Frontend | da fare |
| 9 | Infrastruttura e deploy | da fare |
| 10 | Test | da fare |
| 11 | Documentazione | da fare |
