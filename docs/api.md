# API (Step 3)

Documentazione interattiva generata da OpenAPI: `http://localhost:8000/docs` (schema: `/api/v1/openapi.json`).
Tutte le rotte sono sotto `/api/v1`.

## Autenticazione

1. Il frontend ottiene un **ID token** da Google Identity Services e lo invia a `POST /auth/google`.
2. Il backend lo verifica con la libreria ufficiale `google-auth` (firma, scadenza, issuer, audience = nostro Client ID), poi controlla:
   - email **verificata** da Google;
   - dominio tra quelli ammessi (`ALLOWED_EMAIL_DOMAINS`, default `huware.com`);
   - utente **pre-registrato da un admin** e attivo;
   - al primo accesso salva l'identificativo Google (`google_sub`); se in seguito non coincide, rifiuta.
3. Risponde con un token di sessione (JWT firmato, 8 ore) da inviare come `Authorization: Bearer <token>`.

Il token contiene solo l'id utente: **ruolo e stato attivo si leggono dal database a ogni richiesta**. Disattivare un utente o cambiargli ruolo ha effetto immediato.

Errori di accesso: `401` token assente/non valido/scaduto o utente disattivato; `403` ruolo insufficiente o utente non abilitato; `503` login Google non configurato.

### Sviluppo locale senza Google
`GET /api/v1/config` (pubblico) dice al frontend se mostrare l'accesso con Google (`google_client_id`) e/o quello simulato (`dev_login`). In produzione la documentazione interattiva (`/docs`, `/api/v1/openapi.json`) non è pubblicata.

Con `APP_ENV=local` esiste `POST /auth/dev-login` (`{"email": "..."}`) che emette il token per un utente già registrato. **Non esiste in test e prod** (la rotta non viene registrata). Da Swagger: esegui `dev-login`, copia `access_token`, premi **Authorize** e incollalo.

### Primo amministratore
Imposta `BOOTSTRAP_ADMIN_EMAIL`: all'avvio, **solo se non esiste nessun utente**, viene creato quell'admin. Poi gli utenti li gestisce l'admin.

## Permessi

| Area | Operazione | Admin | Presale | Viewer |
|---|---|:-:|:-:|:-:|
| Auth | `GET /auth/me` | ✅ | ✅ | ✅ |
| Utenti | elenco, dettaglio, creazione, modifica (ruolo, nome, attivo) | ✅ | ❌ | ❌ |
| Clienti | `GET /clients/lookup` (solo id e nome, per i filtri) | ✅ | ✅ | ✅ |
| Clienti | elenco, dettaglio, creazione, modifica | ✅ | ✅ | ❌ |
| Clienti | attivare/disattivare | ✅ | ❌ | ❌ |
| Collaboratori | lettura | ✅ | ✅ | ❌ |
| Collaboratori | creazione, modifica, import CSV | ✅ | ❌ | ❌ |
| Profili e tariffe | lettura (con costi) | ✅ | ✅ | ❌ |
| Profili e tariffe | creazione, modifica, tariffe per anno, import CSV | ✅ | ❌ | ❌ |
| Calendario | lettura | ✅ | ✅ | ❌ |
| Calendario | aggiunta, modifica, eliminazione, import CSV, generazione festività | ✅ | ❌ | ❌ |

I permessi sono applicati **solo dal backend**. Il test `test_permissions_matrix.py` prova ogni operazione con ogni ruolo e senza login, e **fallisce se esiste un endpoint non elencato**: un nuovo endpoint richiede una decisione esplicita sui permessi.

## Convenzioni
- **Paginazione** (utenti, clienti, collaboratori): `?limit=50&offset=0` (massimo 200). Risposta `{items, total, limit, offset}`.
- **Ricerca** `q`: sottostringa senza distinzione di maiuscole; `%` e `_` sono letterali.
- **Importi** come stringhe decimali (`"1800.00"`) per evitare errori di arrotondamento; massimo 2 decimali.
- **Nessuna cancellazione** di utenti, clienti, collaboratori e profili: si **disattivano**. Si eliminano solo righe del calendario e singole tariffe annuali.
- **Protezione dell'ultimo admin**: non si può retrocedere né disattivare l'unico admin attivo (`409`).
- **Conflitti**: nome cliente/profilo/collaboratore duplicato (senza distinzione di maiuscole), email già registrata, data già in calendario → `409`.
- **Audit log**: ogni scrittura (creazione, modifica, import, eliminazione) è registrata con utente, data e valori cambiati. Il primo collegamento a Google è registrato come `link_google`.
- I campi sconosciuti nel corpo delle richieste vengono rifiutati (`422`), per scovare i refusi.

## Import CSV

Formato: UTF-8 (accetta anche l'export Windows di Excel), separatore `;` (anche `,` o tab), intestazioni non sensibili a maiuscole e accenti, righe vuote ignorate, massimo 1 MB e 5000 righe. File di esempio in [`docs/esempi/`](esempi/).

| Endpoint | Colonne | Note |
|---|---|---|
| `POST /employees/import` | `nome; cognome; profilo; attivo` (facoltative: `netsuite_id`, `jira_account_id`) | Crea o aggiorna per nome e cognome. Il profilo deve esistere ed essere attivo. Senza colonna `attivo`, i nuovi sono attivi e gli esistenti non cambiano |
| `POST /profiles/import-rates` | `profilo; anno; prezzo_giorno; costo_giorno` | Crea i profili mancanti e crea o aggiorna la tariffa di quell'anno |
| `POST /calendar/import` | `data; descrizione` (facoltativa) | Aggiunge **chiusure aziendali**. Le date già presenti (anche festività) restano invariate |

**Numeri**: `1.800,00`, `1800,5`, `1800.50`, `€ 1.800` sono tutti accettati. Attenzione: `1.800` si legge come 1800 (punto delle migliaia all'italiana). Booleani: `sì/si/1/true` e `no/0/false`. Date: `gg/mm/aaaa` o `aaaa-mm-gg`.

**Due fasi**: il parametro `dry_run` vale `true` **per default**, quindi un import lanciato senza parametri non scrive nulla e mostra solo l'anteprima con i conteggi (creati / aggiornati / invariati). Per applicare: `?dry_run=false`.

**Tutto o niente**: se anche una sola riga è errata non viene importato nulla. Gli errori sono elencati per numero di riga. In anteprima la risposta è `200` con `errors` valorizzato; con `dry_run=false` e errori la risposta è `422` con lo stesso contenuto.

Le modifiche al listino **non alterano i CE esistenti**, che hanno le tariffe congelate.

Esempio da terminale:
```bash
curl -H "Authorization: Bearer $TOKEN" -F "file=@docs/esempi/listino.csv" \
  "http://localhost:8000/api/v1/profiles/import-rates"                 # anteprima
curl -H "Authorization: Bearer $TOKEN" -F "file=@docs/esempi/listino.csv" \
  "http://localhost:8000/api/v1/profiles/import-rates?dry_run=false"   # conferma
```


---

# Conti economici (Step 5)

Tutte le rotte sono sotto `/api/v1/ce`. L'unità di lavoro è la **versione** di un CE: un CE è l'identità (il codice progetto) e ogni modifica a un CE approvato crea una nuova versione.

## Endpoint

| Operazione | Percorso | Chi |
|---|---|---|
| Crea un CE (versione 1 in bozza) | `POST /ce` | admin, presale |
| Cerca (ultima versione di ogni CE) | `GET /ce` | admin, presale |
| Dettaglio completo, con tutti i risultati | `GET /ce/{id}` | admin, presale |
| Elenco versioni / dettaglio di una versione | `GET /ce/{id}/versions`, `GET /ce/{id}/versions/{n}` | admin, presale |
| Storico delle modifiche | `GET /ce/{id}/history` | admin, presale |
| **Salva l'intero contenuto** | `PUT /ce/{id}/content` | autore o admin |
| **Calcolo di anteprima** (non salva) | `POST /ce/{id}/calculate` | admin, presale |
| Invia in approvazione / ritira | `POST /ce/{id}/submit`, `/withdraw` | autore o admin |
| **Approva** (sempre) / rifiuta (con motivo) | `POST /ce/{id}/approve`, `/reject` | solo admin |
| Nuova versione da un CE approvato | `POST /ce/{id}/versions` | autore o admin |
| Scarta la versione in lavorazione | `DELETE /ce/{id}/open-version` | autore o admin |
| Riallinea tariffe e calendario ai valori correnti | `POST /ce/{id}/realign` | solo admin |
| Duplica come punto di partenza di un nuovo CE | `POST /ce/{id}/duplicate` | admin, presale |
| Elimina (logico) / ripristina | `DELETE /ce/{id}`, `POST /ce/{id}/restore` | solo admin |
| **Elenco ridotto** (ultima versione approvata) | `GET /ce/summaries` | tutti |
| **Dettaglio ridotto** | `GET /ce/summaries/{id}` | tutti |

"Autore" è chi ha creato il CE: il presale modifica solo i propri, l'admin tutti. I presale vedono tutti i CE.

## Stati e transizioni

```
            invia                 approva
 Bozza ─────────────▶ In approvazione ─────────────▶ Approvato ──nuova versione──▶ (v+1 in Bozza)
   ▲  ▲                  │      │
   │  └──── ritira ──────┘      └── rifiuta (motivo) ──▶ Rifiutato ──modifica e reinvia──▶ In approvazione
   └─────────────────────────────────────────────────────────────────────────────────────────┘
```
- **L'admin può approvare sempre**: da bozza, da in approvazione, da rifiutato.
- **In approvazione** il CE è bloccato per il presale (può solo ritirarlo); l'admin può comunque intervenire. Un CE **rifiutato** torna modificabile.
- **Un CE approvato non si modifica mai**: si crea una nuova versione. Può esistere **una sola versione non approvata** per volta; finché non viene approvata, il viewer continua a vedere l'ultima approvata.
- Per inviare o approvare il CE deve avere almeno una riga con ore o percentuali.
- Codici di risposta: `403` ruolo o proprietà non sufficienti, `409` azione non consentita nello stato attuale, `422` dati non validi, `404` CE inesistente o eliminato.

## Creazione e compilazione

`POST /ce` con codice, cliente, progetto, date e modalità. Il sistema:
- porta il codice in maiuscolo (3-100 caratteri: lettere, numeri, punto, trattino, underscore; univoco, anche rispetto ai CE eliminati);
- **congela le tariffe** dal listino dell'anno di inizio (errore chiaro se il listino di quell'anno non esiste);
- precompila i **giorni non lavorativi di ogni mese** dal calendario generale;
- crea le **fasi standard** (Project Management, Analysis, Solution Design, Tech Activities, Testing, Training, Documentation, Go-Live, Stability Period; `standard_phases: false` per partire vuoti).

`PUT /ce/{id}/content` sostituisce in un'unica richiesta testata, giorni non lavorativi per mese, fasi (con contingency), righe (profilo, ore **oppure** % per mese, flag Project Management), milestone. La risposta è il dettaglio completo con il calcolo aggiornato.

```bash
curl -X PUT -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  http://localhost:8000/api/v1/ce/$CE_ID/content -d '{
    "expected_revision": 1,
    "header": {"client_id": "...", "project_name": "Progetto", "start_date": "2026-01-20",
               "end_date": "2026-04-20", "planning_mode": "hours", "max_discount_pct": "10"},
    "non_working_days": [{"month": "2026-01-01", "non_working_days": 5}],
    "phases": [{"name": "Analysis", "contingency_pct": "10", "lines": [
      {"activity": "Interviste", "profile_id": "...", "hours": "24"}]}],
    "milestones": [{"month": "2026-04-01", "label": "GoLive"}]
  }'
```

- **Salvataggio sicuro**: `expected_revision` è il valore letto nell'ultima lettura (`version.revision`). Se nel frattempo qualcuno ha modificato il CE la risposta è `409` con `current_revision` e **nulla viene sovrascritto**.
- **Tariffe dei profili nuovi**: se una riga usa un profilo non ancora presente nel CE, la sua tariffa viene aggiunta dal listino dell'anno del CE (il profilo deve essere attivo e avere la tariffa di quell'anno).
- **Mesi mancanti**: i giorni non lavorativi non indicati si completano dal calendario generale.
- **Errori di validazione**: `422` con `detail.issues`, l'elenco completo dei problemi trovati (non solo il primo).

## Anteprima di calcolo

`POST /ce/{id}/calculate` accetta lo stesso corpo del salvataggio e restituisce il calcolo **senza salvare nulla** (nemmeno le tariffe dei profili nuovi). Serve all'interfaccia per aggiornare i totali mentre si digita, e funziona anche su CE approvati (simulazioni). Il risultato è identico a quello del salvataggio.

## Cosa contiene il dettaglio

`GET /ce/{id}` restituisce `ce`, `version` (stato, revisione, chi ha approvato o rifiutato e perché), `header`, `phases` con le righe, `rates` (tariffe congelate), `milestones`, `calculation` e `actions`.

- `calculation` è l'output del [motore di calcolo](formule.md): mesi, fasi, righe, profili, Servizi Interni / Esterni / Contingency / Totale, staffing mensile, KPI della dashboard, avvisi.
- `actions` dice cosa può fare **l'utente corrente** su questa versione (`edit`, `submit`, `withdraw`, `approve`, `reject`, `new_version`, `discard_version`, `realign`, `delete`), per attivare i pulsanti senza duplicare le regole nel frontend.

## Ricerca

`GET /ce` filtra per `client_id`, `project` (testo), `code` (testo), `date_from` / `date_to`, `status`, `created_by`, con `limit` / `offset`. I filtri di testo cercano una sottostringa senza distinzione di maiuscole.

Il filtro per data cerca i progetti **attivi nel periodo**, cioè quelli il cui periodo si sovrappone all'intervallo; gli estremi sono inclusi. L'elenco mostra l'**ultima versione** di ogni CE, con prezzo, margine % e giornate. Solo l'admin può usare `include_deleted=true`.

## Versioni, riallineamento, duplicazione
- **Nuova versione**: copia tutto (righe, % mensili, tariffe congelate, giorni non lavorativi, milestone). La versione precedente resta consultabile e immutata.
- **Scarta versione**: elimina la versione in lavorazione e torna all'ultima approvata. Non vale per la prima versione (per eliminare un CE serve l'admin).
- **Riallinea** (admin, solo versioni non approvate): aggiorna le tariffe congelate dal listino corrente e/o i giorni non lavorativi dal calendario generale. I valori inseriti a mano sui mesi vengono sovrascritti.
- **Duplica**: crea un nuovo CE in bozza con struttura e righe del sorgente, ma con tariffe e calendario **correnti**. Le percentuali mensili si rimappano mese per mese sul nuovo periodo. Non si copiano max sconto, prezzo firmato, opportunità Salesforce e note.

## Vista ridotta del viewer

`GET /ce/summaries` e `GET /ce/summaries/{id}` mostrano **solo** l'ultima versione approvata e **solo** questi dati: codice, cliente, progetto, date, numero versione, data di approvazione, giornate di management, giornate di delivery, ricavi per fase (contingency inclusa) e totale generale. Costi, margini, ore, righe, tariffe, note e prezzo minimo **non vengono mai inviati**: la risposta è costruita da uno schema dedicato, non filtrata. I CE non approvati o eliminati, per il viewer, non esistono (`404`). Il viewer non può raggiungere nessun altro endpoint dei CE (`403`).

## Storico e audit
Ogni creazione, salvataggio, invio, ritiro, approvazione, rifiuto, nuova versione, scarto, riallineamento, duplicazione, eliminazione e ripristino viene registrato con utente, data e dettagli. `GET /ce/{id}/history` lo mostra, dal più recente.


---

# Notifiche email (Step 6)

Le email partono in automatico dagli eventi (invio in approvazione, approvazione, rifiuto, nuova versione, nuovo utente): vedi [notifiche.md](notifiche.md). Gli endpoint seguenti sono **solo per l'admin**.

| Operazione | Percorso |
|---|---|
| Elenco delle email: stato, tentativi, errore (filtri `status`, `type`, `recipient`, paginazione) | `GET /notifications` |
| Invia subito le email in coda | `POST /notifications/dispatch` |
| Riprova un'email fallita (`409` se non è fallita) | `POST /notifications/{id}/retry` |
| Email di prova all'admin che la richiede | `POST /notifications/test` |

Le operazioni sui CE (`submit`, `approve`, `reject`, nuova versione) e la creazione di un utente **non falliscono mai per colpa delle email**: se Mailjet non risponde, l'operazione va a buon fine e l'email resta in coda.


---

# Export e dashboard (Step 7)

Dettaglio in [export.md](export.md) e [dashboard.md](dashboard.md).

| Operazione | Percorso | Chi |
|---|---|---|
| Esporta un CE (Excel con formule, CSV, PDF; `variant=summary` senza costi) | `GET /ce/{id}/export` | admin, presale |
| Esporta il riepilogo di un CE approvato | `GET /ce/summaries/{id}/export` | tutti |
| Esporta i risultati di una ricerca | `GET /ce/export` | admin, presale |
| Esporta l'elenco ridotto | `GET /ce/summaries/export` | tutti |
| Dashboard portfolio (approvati e, a parte, pipeline) | `GET /dashboard/portfolio` | admin, presale |
| Dashboard carico risorse (FTE, sovraccarico oltre il 100%) | `GET /dashboard/resources` | admin, presale |
| Esporta le dashboard (Excel o CSV) | `GET /dashboard/portfolio/export`, `GET /dashboard/resources/export` | admin, presale |

Le righe di un CE ora riportano anche `employee_name`. Ogni esportazione è registrata nello storico.
