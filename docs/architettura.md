# Architettura

Questa pagina descrive **com'è fatto** il portale e **perché**: serve a chi deve modificarlo, ampliarlo o capirlo in caso di problemi. Per usarlo vedi [guida-utente.md](guida-utente.md); per metterlo in linea [deploy.md](deploy.md).

## Panoramica

```
 Browser (React, responsive)
        │ HTTPS
        ▼
 ┌─────────────────────────── Cloud Run: UN servizio per ambiente ───────────────────────────┐
 │  FastAPI                                                                                    │
 │   ├─ /api/v1/…   API (login, CE, anagrafiche, export, dashboard, notifiche)                 │
 │   └─ tutto il resto: il frontend compilato (index.html, /assets/…) con ricaduta su index    │
 └───────┬───────────────────────┬───────────────────────────────┬──────────────────────────────┘
         │ socket                │ HTTPS                         │ HTTPS
         ▼                       ▼                               ▼
   Cloud SQL (PostgreSQL 16)   Google Identity (verifica        Mailjet (email)
                               il token di accesso)
 Cloud Scheduler ─ogni 5′─► lavoro Cloud Run «mail» (stessa immagine) ─► coda email nel database
 Lavori Cloud Run «migrate» e «seed» (stessa immagine, lanciati a mano o dal flusso di rilascio)
```

Due **ambienti** (`test` e `prod`) in due progetti Google Cloud separati, con la stessa infrastruttura definita da Terraform e **la stessa immagine** (cambia solo la configurazione, che arriva a runtime).

## Principi (le regole che non si rompono)

1. **I calcoli stanno solo nel backend.** Il motore (`backend/app/engine`) è un modulo isolato, senza accesso a database o rete, che lavora in `Decimal`. Il frontend non ricalcola: anche l'anteprima mentre si scrive chiama il server (`POST /ce/{id}/calculate`) con lo stesso motore del salvataggio, quindi i numeri non possono differire.
2. **I permessi sono imposti dal server.** Ogni endpoint dichiara il ruolo richiesto (admin, editor = admin o presale, utente autenticato). Un test percorre **tutti** gli endpoint e verifica che ognuno rifiuti chi non ha il ruolo.
3. **Il viewer è «sicuro per costruzione».** Non è una versione filtrata della vista completa: ha endpoint, schemi di risposta ed esportazioni **dedicati**, che non contengono costi, margini, ore o righe. Non c'è nulla da dimenticare di nascondere. Dei test controllano i file esportati per intero (celle, nomi dei fogli, proprietà, testo del PDF), con una prova di sensibilità.
4. **Tariffe e calendario congelati.** Alla creazione di una versione si copiano prezzo e costo giornalieri dei profili e i giorni non lavorativi: le modifiche successive al listino o al calendario non alterano i CE esistenti (l'admin può riallineare una versione non approvata).
5. **Le versioni approvate sono immutabili.** Una modifica crea una nuova versione. Il salvataggio usa un controllo di **revisione** (concorrenza ottimistica): chi salva su dati nel frattempo cambiati riceve un conflitto e non sovrascrive.
6. **Nessuna email si perde.** Le email passano da una **coda nel database** (tabella `email_outbox`) con chiave anti-doppione e ritentativi crescenti (1′, 5′, 30′, 2h, 6h). Inviare un'email non può far fallire l'azione che l'ha generata.
7. **Un solo servizio, un'immagine per tutti gli ambienti.** Il backend serve anche il frontend; Client ID di Google, database e indirizzi arrivano a runtime. Niente CORS, niente secondo servizio da tenere allineato.
8. **Tutto ciò che conta è tracciato.** Modifiche ai dati e azioni di workflow vanno nell'`audit_log`; le esportazioni sono registrate.
9. **Predisposizione, non integrazione.** Clienti, collaboratori e CE hanno campi per ID esterni (NetSuite, Jira), senza integrazioni attive.

## Il backend (`backend/app`)

| Cartella | Contenuto |
|---|---|
| `engine/` | motore di calcolo: giorni lavorativi, ore → giorni, % → giorni, ricavi, costi, margini, KPI. Puro, senza dipendenze dall'applicazione |
| `models/` | modelli SQLAlchemy: `accounts.py` (utenti, clienti, profili, collaboratori, calendario), `ce.py` (CE, versioni, fasi, righe, allocazioni, milestone, audit, coda email) |
| `schemas/` | schemi Pydantic delle richieste e delle risposte (da cui nasce l'OpenAPI) |
| `services/` | la logica: `ce.py` (creazione, versioni, workflow), `ce_search.py`, `dashboards.py`, `imports.py` (CSV con anteprima), `audit.py`, `bootstrap.py` (primo admin) |
| `api/v1/` | un modulo per area: auth, users, clients, employees, profiles, calendar, ce, exports, dashboard, notifications, health (con `/config`) |
| `exports/` | Excel con formule vere, CSV, PDF, varianti riepilogo e dashboard |
| `notifications/` | coda, mittente (Mailjet o console), modelli, comando `python -m app.notifications` per l'invio periodico |
| `core/`, `db/` | impostazioni, sicurezza (JWT), sessione, dati iniziali (`python -m app.db.seed`) |
| `web.py`, `security.py`, `logging_config.py` | frontend servito dal backend, intestazioni di sicurezza, log in JSON |

**Una richiesta tipica**: il router verifica il ruolo → chiama un servizio → il servizio legge/scrive il database e, se serve, chiama il motore → il router restituisce uno schema Pydantic. I router non contengono logica.

**Accesso**: il browser ottiene un token Google (Google Identity Services), lo invia a `POST /auth/google`; il server lo verifica con Google, controlla che l'email sia di un utente **registrato e attivo** nel dominio ammesso, e restituisce un **JWT** proprio (8 ore). Il token sta in `sessionStorage`: scompare chiudendo la scheda. Un 401 chiude la sessione. Solo con `APP_ENV=local` esiste l'accesso simulato.

**Database**: 17 tabelle (vedi [modello-dati.md](modello-dati.md)). Le regole importanti sono vincoli del database (unicità, valori ammessi, percentuali 0–100, tentativi non negativi…), non solo controlli dell'applicazione. Le migrazioni sono Alembic, eseguite dal lavoro `migrate` **prima** del codice nuovo e quindi scritte in modo compatibile col codice precedente.

## Il frontend (`frontend/src`)

React 18 + TypeScript + Vite + Tailwind + TanStack Query + React Router. Italiano e euro. I **tipi dell'API sono generati** dallo schema OpenAPI (`make api-types`): se il backend cambia, la CI avvisa che i tipi sono da rigenerare. Le logiche non banali (bozza dell'editor, numeri all'italiana, incolla da Excel, controlli immediati) sono funzioni pure in `editor/` e `lib/`, provate da test unitari. I grafici sono SVG scritti a mano, senza librerie, con tabella equivalente per i lettori di schermo. La pagina di accesso chiede al server cosa mostrare (`/api/v1/config`).

## Sicurezza

| Strato | Cosa c'è |
|---|---|
| Accesso | Google, solo utenti registrati e attivi, dominio ammesso; JWT a scadenza |
| Autorizzazione | ruoli imposti dal server, test su ogni endpoint; viewer con schemi dedicati |
| Trasporto e browser | solo HTTPS con HSTS; CSP (solo il portale e Google Sign-In), niente incorporamento in altri siti, niente MIME sniffing; risposte API con `no-store` |
| Dati | database senza reti autorizzate, solo connessioni cifrate, accessibile solo dal servizio; backup giornalieri e, in produzione, recupero a un istante preciso; protezione dall'eliminazione |
| Segreti | in Secret Manager, letti solo dall'account di esecuzione; chiave delle sessioni e password del database generate da Terraform |
| Pubblicazione | GitHub senza chiavi (Workload Identity Federation) limitato al repository; permessi minimi; approvazione umana per la produzione |
| Export | protezione dall'esecuzione di formule in CSV ed Excel; riservatezza del viewer verificata sui file |
| Rimane fuori | limite alle richieste (rate limiting), accesso con Identity-Aware Proxy o VPN, consultazione dell'audit log nell'interfaccia |

## Affidabilità e osservabilità

- **Avvii a freddo**: con `min_instances = 0` il primo accesso dopo una pausa impiega qualche secondo.
- **Concorrenza**: 40 richieste per istanza, fino a 3 (test) o 5 (produzione) istanze. Per un uso interno è largamente sufficiente.
- **Salute**: `GET /api/v1/health`; controllo di raggiungibilità ogni 5 minuti con avviso per email; avvisi per errori 5xx e lavori falliti.
- **Log**: JSON su Cloud Logging (campo `severity`), filtrabili per livello.
- **Limiti noti**: una sola regione (`europe-west8`): se la regione non è disponibile, il portale non lo è; il ripristino è da backup in un'altra regione, non automatico.

## Come si verifica (e quanto)

| Livello | Cosa | Dove |
|---|---|---|
| Backend | motore di calcolo validato sul foglio reale; API, workflow, permessi, export, dashboard, migrazioni, notifiche, esecuzione su Cloud Run | `backend/tests` (oltre 900 test) |
| Frontend, unità | modello dell'editor, numeri, grafici, finestre, azioni | `frontend/src/__tests__` |
| Browser | tutti i percorsi principali, su desktop e smartphone, con controlli di accessibilità WCAG AA | `frontend/e2e` (Playwright) |
| Infrastruttura | modulo Terraform con provider simulati; script con `shellcheck`; flussi con `actionlint`; Dockerfile con `hadolint`; strumento di collaudo con `gcloud` simulato | `infra/…/tests`, `backend/tests` |
| Ambiente reale | controllo automatico + prove nel browser | [collaudo.md](collaudo.md) |

Molti test sono stati controllati anche «al contrario»: si introduce di proposito un errore nel codice e si verifica che i test lo individuino.

## CI/CD

`push` su `main` → CI (test backend con le versioni fissate, frontend, schema dell'API, prove nel browser, immagine) → se verde, **Deploy**: costruisce l'immagine una volta, la prova, la pubblica, esegue le migrazioni e aggiorna il **test**; dopo l'approvazione fa lo stesso sulla **produzione**. Le versioni delle librerie sono fissate (`backend/requirements*.lock`, `package-lock.json`): nulla cambia finché non si aggiorna di proposito.

## Dove mettere le mani

| Voglio… | Cosa toccare |
|---|---|
| cambiare una formula | `engine/calculate.py` + `docs/formule.md` + test del motore (e il confronto con `tests/fixtures/ce_bonga.json`) |
| aggiungere un campo al CE | modello + migrazione (`make migration m="…"`) + schema + servizio + `make api-types` + frontend + export, se serve |
| aggiungere un endpoint | router in `api/v1` + schema + servizio + dichiarare il ruolo + test del permesso + `make api-types` |
| aggiungere una scheda di amministrazione | pagina in `frontend/src/pages/admin`, rotta in `App.tsx`, scheda in `AdminHeader`, test del browser |
| cambiare un'impostazione | `core/config.py` + Terraform (`main.tf` del modulo) + `docs/deploy.md` (appendice) |
| aggiornare le librerie | `make lock` e `make api-types` (vedi [manutenzione.md](manutenzione.md)) |
