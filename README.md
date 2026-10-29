# Portale Conti Economici (CE) di progetto

Portale web interno di Huware per creare, memorizzare, modificare e ricercare i **conti economici** di progetto: costi, ricavi, marginalità e impegno delle risorse, con flusso di approvazione, export (Excel con formule vere, PDF, CSV) e dashboard.

## Stack

| Livello | Tecnologia |
|---|---|
| Backend | Python 3.12, FastAPI (OpenAPI), SQLAlchemy 2, Alembic |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS (servito dallo stesso servizio del backend) |
| Database | PostgreSQL 16 (Cloud SQL su Google Cloud) |
| Hosting | Google Cloud Run, regione `europe-west8`, ambienti `test` e `prod` in progetti separati |
| Infrastruttura | Terraform, Docker, Secret Manager, Cloud Scheduler |
| CI/CD | GitHub Actions (senza chiavi: Workload Identity Federation) |
| Email | Mailjet |

## Struttura del repository

```
backend/    API FastAPI, modello dati, motore di calcolo (app/engine), test
frontend/   interfaccia React (responsive), test unitari e nel browser (Playwright)
infra/      Terraform (modulo + ambienti test e prod), script (smoke, collaudo, bootstrap)
docs/       documentazione
.github/    flussi: CI, Deploy, controlli sull'infrastruttura
Dockerfile  immagine unica per tutti gli ambienti
```

## Documentazione, per chi sei

**Uso il portale**
- [Guida all'uso](docs/guida-utente.md): accesso, creare e compilare un CE, approvazione, export, dashboard, amministrazione.
- [Analisi funzionale](docs/analisi-funzionale.md): le regole del portale, approvate.
- [Formule](docs/formule.md): come si calcolano giornate, ricavi, margini.

**Gestisco il portale**
- [Pubblicazione su Google Cloud](docs/deploy.md): installazione, rilascio, operazioni, cosa fare se qualcosa non va.
- [Collaudo sull'ambiente reale](docs/collaudo.md): controllo automatico, prove nel browser, passaggio in produzione.
- [Manutenzione ed emergenze](docs/manutenzione.md): compiti mensili, trimestrali e annuali; cosa fare nei casi di emergenza; cosa resta aperto.
- [Registro delle modifiche](docs/changelog.md): tutte le richieste di modifica e di nuove funzionalità, dalla più recente, con decisioni, verifiche e stato.

**Sviluppo il portale**
- [Architettura](docs/architettura.md): com'è fatto e perché; dove mettere le mani.
- [Presentazione tecnica](docs/presentazione-tecnica.html): pagina unica, da aprire nel browser, con architettura, modello dati, API, sicurezza e storia delle richieste.
- [Modello dati](docs/modello-dati.md) · [API](docs/api.md) · [Notifiche email](docs/notifiche.md) · [Export](docs/export.md) · [Dashboard](docs/dashboard.md) · [Frontend](docs/frontend.md)
- [Convenzioni di sviluppo](CONTRIBUTING.md)

## Avvio in locale

Prerequisiti: Python 3.12, Node 20+, Docker (per PostgreSQL).

```bash
make install     # dipendenze backend e frontend
cp .env.example backend/.env
make db          # PostgreSQL locale (se la porta 5432 è occupata: DB_PORT=5433 make db)
make migrate     # crea lo schema
make seed        # profili, tariffe 2026, festività
make backend     # API su http://localhost:8000  (documentazione: /docs)
make demo        # 8 CE di esempio, in un altro terminale (serve il backend acceso)
make frontend    # interfaccia su http://localhost:5173
```

Per entrare in locale senza Google: in `backend/.env` imposta `BOOTSTRAP_ADMIN_EMAIL=tua.email@huware.com`, riavvia il backend e scegli «Entra senza Google» nella pagina di accesso. L'accesso simulato esiste **solo** con `APP_ENV=local`.

Altri comandi utili: `make test`, `make lint`, `make api-types`, `make migration m="descrizione"`, `make lock`, `make docker-build`. L'elenco completo con `make help`.

## Stato del progetto

| Passo | Descrizione | Stato |
|---|---|---|
| 1–7 | Repository, modello dati, backend, motore di calcolo, API dei CE, notifiche, export e dashboard (API) | completati |
| 8 | Frontend: accesso, elenco, dettaglio, modifica, approvazione, dashboard, amministrazione | completato |
| 9 | Infrastruttura e pubblicazione ([deploy](docs/deploy.md)) | **completato sul test**; produzione predisposta, da pubblicare |
| 10 | Collaudo sull'ambiente reale ([collaudo](docs/collaudo.md)) | strumenti e guida pronti; **test funzionante**, collaudo formale e produzione da eseguire |
| 11 | Documentazione | completata |

Cosa resta aperto (logo vettoriale, font da confermare, chiusure aziendali, dominio proprio, …) è nell'ultima sezione di [manutenzione.md](docs/manutenzione.md).
