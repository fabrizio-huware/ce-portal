# API (Step 3)

Documentazione interattiva generata da OpenAPI: `http://localhost:8000/docs` (schema: `/api/v1/openapi.json`). **In produzione è spenta** (né `/docs` né lo schema sono esposti).

**Leggere le API senza avviare nulla**: `make api-docs` scrive `api-swagger.html`, la stessa documentazione Swagger in **un solo file** (circa 2 MB) che si apre con un doppio clic, anche offline. È una copia di **sola lettura** dello schema (`frontend/openapi.json`): le chiamate di prova si fanno in locale, perché dal file il browser le bloccherebbe (il portale accetta solo la propria origine). Serve `npm` solo per scaricare Swagger UI; va rigenerato quando le API cambiano.
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
- **Nessuna cancellazione** di utenti, clienti, collaboratori, practice e profili: si **disattivano**. Si eliminano solo righe del calendario e singole tariffe annuali.
- **Protezione dell'ultimo admin**: non si può retrocedere né disattivare l'unico admin attivo (`409`).
- **Conflitti**: nome cliente/profilo/collaboratore duplicato (senza distinzione di maiuscole), email già registrata, data già in calendario → `409`.
- **Audit log**: ogni scrittura (creazione, modifica, import, eliminazione) è registrata con utente, data e valori cambiati. Il primo collegamento a Google è registrato come `link_google`.
- I campi sconosciuti nel corpo delle richieste vengono rifiutati (`422`), per scovare i refusi.

## Import CSV

Formato: UTF-8 (accetta anche l'export Windows di Excel), separatore `;` (anche `,` o tab), intestazioni non sensibili a maiuscole e accenti, righe vuote ignorate, massimo 1 MB e 5000 righe. File di esempio in [`docs/esempi/`](esempi/).

| Endpoint | Colonne | Note |
|---|---|---|
| `POST /employees/import` | `nome; cognome; profilo; attivo` (facoltative: `practice`, `netsuite_id`, `jira_account_id`) | Crea o aggiorna per nome e cognome. Il profilo e la practice devono esistere ed essere attivi: una practice sconosciuta o disattivata blocca tutto, con il numero di riga. Senza la colonna `practice` (o con la cella vuota) i nuovi ricevono «Da assegnare» e gli esistenti non cambiano. Senza colonna `attivo`, i nuovi sono attivi e gli esistenti non cambiano |
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

## Practice e collaboratori

Ogni collaboratore ha **una practice** (area di competenza), obbligatoria. Non compare nelle righe dei CE: serve ai report del carico.

| Operazione | Percorso | Chi |
|---|---|---|
| Elenco con i collaboratori attivi di ciascuna | `GET /practices` | admin |
| Elenco minimo per filtri e menu (anche disattivate) | `GET /practices/lookup` | admin, presale |
| Crea (nome unico senza distinzione di maiuscole, `409` se esiste) | `POST /practices` | admin |
| Rinomina, attiva e disattiva | `PATCH /practices/{id}` | admin |

- La practice di sistema **«Da assegnare»** non si rinomina né si disattiva (`409`). Una practice disattivata resta ai collaboratori che già la hanno ma non si può scegliere per altri (`422`).
- `POST /employees`: `practice_id` facoltativo (senza, «Da assegnare»); `PATCH /employees/{id}` non accetta `practice_id: null`. Le risposte dei collaboratori hanno `practice_id` e `practice_name`; l'elenco si filtra con `?practice_id=`.

## Business unit

Le business unit stanno sopra le practice: `GET /api/v1/business-units/lookup` (admin, presale e responsabili: id, nome e stato di tutte, anche le disattivate) per filtri e menu; `GET`, `POST` e `PATCH /api/v1/business-units` (solo admin) per elenco con i conteggi (`practices_count`, `employees_count`, `users_count`), creazione e modifica. Non si eliminano: si disattivano.

- **Business unit di sistema «Da assegnare»**: `409` se si prova a rinominarla o disattivarla.
- **Nome unico** senza distinzione di maiuscole (`409`).
- **Practice**: `PracticeOut` ha `business_unit_id` e `business_unit_name`; in creazione `business_unit_id` è facoltativo (senza, va in «Da assegnare»); `422` se la business unit non esiste o è disattivata (confermare quella che la practice ha già è sempre ammesso), e se si prova a metterla a `null`.
- **Collaboratori**: `EmployeeOut` mostra `business_unit_id` e `business_unit_name`, derivati dalla practice.
- **Utenti**: `UserOut` ha `business_unit_id` e `business_unit_name`; `UserCreate` e `UserUpdate` accettano `business_unit_id`. Solo il ruolo `presale` e il nuovo `bu_manager` (responsabile di business unit) ne hanno una; per il responsabile è obbligatoria (`422` senza). A una persona non si assegna «Da assegnare». Chi cambia ruolo e non è più presale né responsabile la perde.
- **Business unit nel CE**: `POST /api/v1/ce` richiede `business_unit_ids` (almeno una; `422` se vuoto, inesistente, «Da assegnare» o disattivata). Il vecchio campo `header.business_unit` si accetta ma **si ignora**: il testo lo ricava il server. `PUT /api/v1/ce/{id}/business-units` (`{"business_unit_ids": [...]}`; solo autore o admin) sostituisce l'elenco: `409` se l'ultima versione non è in bozza o rifiutata (salvo la riparazione di un CE senza business unit da parte di un admin), `403` per chi non è l'autore. Il dettaglio dice `business_units`, le `undeclared_business_units` (business unit dei collaboratori delle righe non coinvolte: l'invio è bloccato con `422`), e `actions.set_business_units`; l'elenco dei CE ha `business_units` (nomi). La duplicazione (`business_unit_ids` facoltativo) copia quelle dell'origine.
- **Dashboard per business unit**: `GET /dashboard/portfolio` (e la sua esportazione) accetta `business_unit_id` (i CE che coinvolgono quella business unit; il vecchio filtro di testo `business_unit` resta). `GET /dashboard/resources` (e la sua esportazione) accetta `business_unit_id` (solo le persone di quella business unit) e `project` (testo contenuto nel nome del progetto o nel codice; con la visibilità accesa si cercano solo i CE che l'utente vede) e risponde con una nuova sezione `business_units` (una riga per business unit: persone con impegno e percentuale, come per le practice) e con `business_unit_name` sulle righe dei collaboratori e delle practice. Esportazioni del Carico risorse: nuovo foglio Excel «Business unit» (prima di «Practice») e nuova colonna **in coda** «Business unit» nel foglio «Dati» e nel CSV, che ha anche le righe di tipo «Business unit». Con la visibilità accesa un presale o un responsabile non può guardare un'altra business unit nel Carico risorse: riceve un elenco vuoto.
- **Visibilità per business unit**: `GET` e `PUT /api/v1/business-units/visibility` (solo admin; `{"enabled": bool}`) leggono e cambiano l'interruttore (spento alla pubblicazione) e dicono che cosa manca prima di accendere (`report`: CE senza business unit con i primi 20 codici, presale senza business unit, practice ancora in «Da assegnare»). **Acceso**, per un presale o un responsabile ogni rotta con un `{ce_id}` di un CE che non vede (non coinvolge la sua business unit e non è suo) risponde `404 «CE non trovato»` **prima** di qualunque altro controllo; l'elenco, la sua esportazione e il Portfolio contano solo i CE visibili; il Carico risorse mostra solo le persone della sua business unit. Admin, viewer e integrazioni non cambiano.
- **Approvazione**: `POST /ce/{id}/approve` e `/reject` sono ora per gli «editor»: l'admin sempre; il responsabile di business unit solo per un CE **in approvazione** che coinvolge la sua business unit (`403` altrimenti); un presale mai. Il dettaglio dice se si può con `actions.approve` e `actions.reject`.
- **CE esistenti**: `POST /api/v1/business-units/apply-to-existing-ces` (solo admin, idempotente) assegna le business unit ai CE che non ne hanno e dice quanti ha aggiornato e quali restano senza.
- **Ruolo `bu_manager`**: ha gli stessi accessi del presale (rotte «editor») e non quelle dell'admin. L'approvazione dei CE che coinvolgono la sua business unit arriva con le prossime consegne.

## Esito della trattativa (Close Won / Close Lost)

`PUT /api/v1/ce/{id}/outcome` (admin, presale e responsabili) con `{"outcome": "won" | "lost" | null, "note": "..."}`: imposta, cambia o toglie l'esito (`null` lo toglie; la nota è facoltativa e non ammessa senza esito, `422`). Solo se l'**ultima versione è approvata** (`409`), e solo per l'admin, il responsabile di una business unit coinvolta e l'autore (`403` agli altri). Risponde con il dettaglio del CE.

- **Dettaglio** (`GET /ce/{id}`): `outcome` con `value`, `at`, `by` e `note`; `actions.set_outcome` dice se l'utente può gestirlo; `actions.delete` è falso e `actions.delete_blocked_reason` spiega perché quando il CE ha un esito (`DELETE` risponde `409`); `actions.new_version` è falso dopo Close Lost (`POST /ce/{id}/versions` risponde `409`).
- **Elenco**: ogni elemento ha `outcome`; filtro `outcome=none|won|lost` (vale anche per `GET /ce/export`).
- **Viewer e integrazioni**: `outcome` (solo il valore, mai la nota) nell'elenco e nel riepilogo, in **sola lettura**: le integrazioni non possono impostarlo.

## Integrazioni (programmi esterni)

Un programma esterno si identifica con l'**ID token Google del suo account di servizio**, con audience uguale all'indirizzo del portale (`S2S_AUDIENCES`), e lo manda come `Authorization: Bearer`. Il portale ne controlla firma, scadenza, issuer e audience, cerca l'email in un elenco gestito dagli amministratori (`/integrations`: registra, modifica permessi, disattiva) e legge **a ogni richiesta** se l'integrazione è attiva e quali permessi ha. Al massimo **una richiesta al secondo** per integrazione (`429` con `Retry-After`).

| Operazione | Percorso | Permesso |
|---|---|---|
| Clienti, profili, collaboratori e business unit attivi (solo identificativo e nome; le business unit senza quella di sistema) | `GET /integrazioni/anagrafiche/{clienti,profili,collaboratori,business-unit}` | `read` |
| Elenco dei CE di qualunque stato | `GET /integrazioni/ce` | `read` |
| Crea un CE con tutto il contenuto (tutto o niente; `external_ref` lo rende ripetibile; **`business_unit_ids` obbligatorio**, almeno una) | `POST /integrazioni/ce` | `create` |
| Riepilogo di un CE (giornate e ricavi) | `GET /integrazioni/ce/{id}` | `read` |
| Rilegge il contenuto di un proprio CE | `GET /integrazioni/ce/{id}/content` | `read` |
| Sostituisce il contenuto di una propria bozza (`expected_revision`) | `PUT /integrazioni/ce/{id}/content` | `edit` |
| PDF di riepilogo (giornate e ricavi) | `GET /integrazioni/ce/{id}/pdf` | `export` |
| Registra, elenca, modifica o disattiva le integrazioni (solo admin) | `/integrations` | admin |
| Assegna a un presale un CE creato da un'integrazione (solo admin) | `POST /ce/{id}/assign` | admin |

Le business unit coinvolte le indica l'integrazione **solo alla creazione** (`business_unit_ids`, da `/anagrafiche/business-unit`); dopo, le cambiano l'autore e gli amministratori dall'interfaccia, e una creazione ripetuta con lo stesso `external_ref` non le tocca. Il campo `business_unit` nella testata si ignora. Nessuna risposta contiene costi, margini o tariffe. I CE non approvati hanno un avviso («Versione non approvata»). L'integrazione modifica solo i CE che ha creato e che nessuno ha ancora assegnato; non invia in approvazione né approva (lo fa una persona). Dopo l'assegnazione a un presale il CE resta leggibile ma non più modificabile dall'integrazione.

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
| **Approva** (sempre) / rifiuta (con motivo) | `POST /ce/{id}/approve`, `/reject` | admin; responsabile di una business unit coinvolta (solo un CE in approvazione) |
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

`GET /ce` filtra per `client_id`, `project` (testo), `code` (testo), `date_from` / `date_to`, `status`, `created_by`, **`business_unit_id`** (i CE che coinvolgono quella business unit; vale anche per `GET /ce/export`), con `limit` / `offset`. I filtri di testo cercano una sottostringa senza distinzione di maiuscole.

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
| Esporta un CE (Excel con formule, CSV, PDF con la divisione per business unit; `variant=summary` senza costi) | `GET /ce/{id}/export` | admin, presale |
| Esporta il riepilogo di un CE approvato | `GET /ce/summaries/{id}/export` | tutti |
| Esporta i risultati di una ricerca | `GET /ce/export` | admin, presale |
| Esporta l'elenco ridotto | `GET /ce/summaries/export` | tutti |
| Dashboard portfolio (approvati e, a parte, pipeline) | `GET /dashboard/portfolio` | admin, presale |
| Dashboard carico risorse (FTE, sovraccarico oltre il 100%; per collaboratore, **practice** e profilo) | `GET /dashboard/resources` | admin, presale |
| Esporta le dashboard (Excel o CSV) | `GET /dashboard/portfolio/export`, `GET /dashboard/resources/export` | admin, presale |

Le righe di un CE ora riportano anche `employee_name`. Ogni esportazione è registrata nello storico.
