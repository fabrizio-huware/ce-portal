# Modello dati

Schema PostgreSQL gestito con Alembic (`backend/migrations`). I modelli SQLAlchemy sono in `backend/app/models`.

## Convenzioni
- Chiavi primarie UUID generate dal database (`gen_random_uuid()`); eccezione: `audit_log` (intero progressivo) e le tabelle con chiave composta naturale (`profile_rates`, `ce_version_rates`, `ce_line_allocations`).
- `created_at` / `updated_at` in UTC (`timestamptz`) su tutte le tabelle tranne `audit_log`.
- Importi `NUMERIC(14,2)`, percentuali `NUMERIC(5,2)` (0-100), ore `NUMERIC(10,2)`.
- Stati e tipi sono testo con vincolo `CHECK` (più semplice da evolvere degli enum nativi).
- Vincoli e indici hanno nomi deterministici (`pk_`, `fk_`, `uq_`, `ck_`, `ix_`).
- Nessuna cancellazione fisica di dati in uso: chiavi esterne `RESTRICT`; i CE si cancellano logicamente (`deleted_at`). Il contenuto di una versione (fasi, righe, allocazioni, milestone, tariffe) si elimina a cascata con la versione.

## Diagramma ER

```mermaid
erDiagram
  USERS {
    uuid id PK
    string email UK
    string full_name
    string role "admin | presale | bu_manager | viewer"
    boolean is_active
    string google_sub UK
    timestamp last_login_at
    boolean is_service "utente di servizio di un'integrazione"
    uuid business_unit_id FK "solo presale e responsabili"
  }
  BUSINESS_UNITS {
    uuid id PK
    string name UK "unico senza distinzione di maiuscole; «Da assegnare» è di sistema"
    boolean is_active
  }
  INTEGRATIONS {
    uuid id PK
    string name
    string service_account_email UK "minuscolo"
    string service_account_sub UK "si lega alla prima chiamata"
    uuid user_id FK UK "utente di servizio"
    string_array permissions "create | edit | read | export"
    boolean is_active
    timestamp last_used_at
    uuid created_by FK
  }
  CLIENTS {
    uuid id PK
    string name UK "unico, case-insensitive"
    string address
    string external_ref
    boolean is_active
  }
  PROFILES {
    uuid id PK
    string name UK
    boolean is_active
    boolean is_external "profilo Esterni"
    int sort_order
    string band
    numeric billability_target
  }
  PROFILE_RATES {
    uuid profile_id PK, FK
    int year PK
    numeric daily_price
    numeric daily_cost
  }
  PRACTICES {
    uuid id PK
    string name UK "unico senza distinzione di maiuscole"
    boolean is_active
    uuid business_unit_id FK "obbligatoria"
  }
  EMPLOYEES {
    uuid id PK
    string first_name
    string last_name
    uuid default_profile_id FK
    uuid practice_id FK "obbligatoria"
    boolean is_active
    string netsuite_id
    string jira_account_id
  }
  NON_WORKING_DAYS {
    uuid id PK
    date day UK
    string kind "holiday | company_closure"
    string description
  }
  CE {
    uuid id PK
    string code UK "unico, case-insensitive"
    uuid created_by FK "autore; per i CE di un'integrazione, finché non è assegnato, l'utente di servizio"
    timestamp deleted_at
    uuid deleted_by FK
    uuid integration_id FK "integrazione che lo ha creato (non cambia)"
    string external_ref "identificativo scelto dall'integrazione, unico con integration_id"
    string requested_by "email di chi lo ha chiesto (informativo)"
    string outcome "won | lost: esito della trattativa, solo con l'ultima versione approvata"
    timestamp outcome_at
    uuid outcome_by FK
    string outcome_note "il motivo: facoltativo"
  }
  APP_SETTINGS {
    string key PK "es. bu_visibility_enabled"
    jsonb value
    timestamp updated_at
    uuid updated_by FK "chi l'ha cambiata"
  }
  CE_BUSINESS_UNITS {
    uuid ce_id PK, FK "cancellando il CE spariscono"
    uuid business_unit_id PK, FK "una business unit usata non si cancella"
  }
  CE_VERSIONS {
    uuid id PK
    uuid ce_id FK
    int version_number
    string status "draft | submitted | approved | rejected"
    uuid client_id FK
    string project_name
    string sf_opportunity
    string business_unit "etichetta ricavata dal server dalle business unit coinvolte (obsoleta come campo da compilare)"
    string notes
    date start_date
    date end_date
    string planning_mode "hours | percent"
    int rate_year
    numeric signed_price
    numeric max_discount_pct "inserito da chi compila"
    int revision "salvataggio sicuro"
    jsonb summary "totali sempre pronti"
    uuid created_by FK
    timestamp submitted_at
    uuid approved_by FK
    timestamp approved_at
    uuid rejected_by FK
    timestamp rejected_at
    string rejection_reason
    jsonb approved_totals
  }
  CE_VERSION_RATES {
    uuid version_id PK, FK
    uuid profile_id PK, FK
    numeric daily_price
    numeric daily_cost
  }
  CE_VERSION_MONTHS {
    uuid version_id PK, FK
    date month PK
    int non_working_days "inseriti a mano per mese"
  }
  CE_PHASES {
    uuid id PK
    uuid version_id FK
    int position
    string name
    numeric contingency_pct
  }
  CE_LINES {
    uuid id PK
    uuid phase_id FK
    int position
    string activity
    uuid profile_id FK "anche Esterni"
    uuid employee_id FK
    boolean is_project_management
    numeric hours
  }
  CE_LINE_ALLOCATIONS {
    uuid line_id PK, FK
    date month PK
    numeric allocation_pct
  }
  CE_MILESTONES {
    uuid id PK
    uuid version_id FK
    date month
    string label
  }
  AUDIT_LOG {
    bigint id PK
    timestamp occurred_at
    uuid user_id FK
    string entity_type
    uuid entity_id
    string action
    jsonb changes
  }
  EMAIL_OUTBOX {
    uuid id PK
    string type
    string recipient
    jsonb payload
    string status "pending | sent | failed"
    int attempts
    timestamp sent_at
    string error
    string dedupe_key UK "una sola email per evento"
    timestamp next_attempt_at
    timestamp last_attempt_at
    string provider_message_id
  }

  PROFILES ||--o{ PROFILE_RATES : "tariffe per anno"
  PROFILES ||--o{ EMPLOYEES : "profilo di default"
  BUSINESS_UNITS ||--o{ PRACTICES : "contiene"
  BUSINESS_UNITS ||--o{ USERS : "presale e responsabili"
  PRACTICES ||--o{ EMPLOYEES : "practice"
  CE ||--|{ CE_VERSIONS : "versioni"
  CE ||--o{ CE_BUSINESS_UNITS : "business unit coinvolte"
  BUSINESS_UNITS ||--o{ CE_BUSINESS_UNITS : "coinvolta in"
  CLIENTS ||--o{ CE_VERSIONS : "cliente"
  CE_VERSIONS ||--|{ CE_VERSION_RATES : "tariffe congelate"
  CE_VERSIONS ||--|{ CE_VERSION_MONTHS : "giorni non lavorativi"
  PROFILES ||--o{ CE_VERSION_RATES : "origine"
  CE_VERSIONS ||--|{ CE_PHASES : "fasi"
  CE_VERSIONS ||--o{ CE_MILESTONES : "milestone"
  CE_PHASES ||--|{ CE_LINES : "righe"
  PROFILES ||--o{ CE_LINES : "profilo"
  EMPLOYEES ||--o{ CE_LINES : "collaboratore"
  CE_LINES ||--o{ CE_LINE_ALLOCATIONS : "% per mese"
  USERS ||--o{ CE : "creato da"
  USERS ||--o| INTEGRATIONS : "utente di servizio"
  INTEGRATIONS ||--o{ CE : "creati dall'integrazione"
  USERS ||--o{ AUDIT_LOG : "autore"
```

## Regole imposte dal database

| Regola | Vincolo |
|---|---|
| Ruolo utente tra admin, presale, viewer | `ck_users_role_valid` |
| Email utente minuscola e unica | `ck_users_email_lowercase`, `uq_users_email` |
| Nome cliente e codice CE unici senza distinzione di maiuscole | `uq_clients_name_lower`, `uq_ce_code_lower` |
| Una tariffa per profilo e anno; importi non negativi | `pk_profile_rates`, `ck_profile_rates_*` |
| Data fine ≥ data inizio | `ck_ce_versions_dates_ordered` |
| Stato e modalità di pianificazione validi | `ck_ce_versions_status_valid`, `..._planning_mode_valid` |
| Versione approvata: approvatore, data e totali obbligatori | `ck_ce_versions_approved_fields` |
| Versione rifiutata: chi e quando obbligatori | `ck_ce_versions_rejected_fields` |
| Numero versione unico per CE | `uq_ce_versions_ce_id_version_number` |
| **Una sola versione non approvata per CE** | `uq_ce_versions_one_open` (indice univoco parziale) |
| Contingency tra 0 e 100 | `ck_ce_phases_contingency_range` |
| Ogni riga ha un profilo (i servizi esterni usano il profilo Esterni) e ore non negative | `profile_id NOT NULL`, `ck_ce_lines_hours_non_negative` |
| Max sconto tra 0 e 100; revisione ≥ 1 | `ck_ce_versions_max_discount_range`, `ck_ce_versions_revision_positive` |
| Giorni non lavorativi per mese: tra 0 e 23, mese al primo giorno, uno per mese | `ck_ce_version_months_*`, `pk_ce_version_months` |
| Allocazione tra 0 e 100%, una per riga e mese | `ck_ce_line_allocations_allocation_pct_range`, `pk_ce_line_allocations` |
| Mesi di allocazioni e milestone sempre al primo giorno | `ck_..._month_first_day` |

Le regole che coinvolgono più tabelle (es. "le ore si usano solo se il CE è in modalità ore", "durata massima 12 mesi", "una versione approvata non si modifica") sono applicate dal backend (Step 5) e coperte da test.

## Ricerca
Estensione `pg_trgm` con indici GIN su `ce.code`, `ce_versions.project_name` e `clients.name` per la ricerca parziale (`ILIKE '%testo%'`); indici su stato e date.

> **Nota Cloud SQL (Step 9):** `CREATE EXTENSION pg_trgm` richiede un utente con privilegi sufficienti (es. l'utente `postgres` di Cloud SQL). La migrazione iniziale la esegue con `IF NOT EXISTS`.

## Dati iniziali
`make seed` carica (senza duplicare né sovrascrivere modifiche dell'admin): 8 profili con tariffe 2026 dal foglio "EC - COSTO AZIENDALE" (esclusi "Esterni" e le bande), e le festività nazionali 2026-2027 più Sant'Ambrogio. Le chiusure aziendali si inseriscono da interfaccia admin.

## Evolvere lo schema
1. Modifica i modelli in `backend/app/models`.
2. `make migration m="descrizione"` e **rivedi sempre** il file generato in `backend/migrations/versions`.
3. `make test`: il test `test_models_and_migration_are_in_sync` fallisce se modelli e migrazioni divergono.

## Migrazione `0002` (Step 5)

Applicata e collaudata in entrambe le direzioni, anche con dati preesistenti:

- **`ce_version_months`** (nuova): giorni non lavorativi inseriti a mano per ogni mese del progetto, come nel foglio. Precompilata dal calendario generale alla creazione, congelata nella versione.
- **`profiles.is_external`**: il profilo **Esterni** (seed: 750 / 360 al giorno per il 2026) è un normale profilo del listino con questo indicatore; le sue righe confluiscono in Servizi Esterni.
- **`ce_versions`**: `max_discount_pct` (max sconto), `revision` (contatore del salvataggio sicuro: cambia a ogni modifica) e `summary` (totali aggiornati a ogni salvataggio, per elenchi veloci; `approved_totals` li congela all'approvazione).
- **`ce_lines`**: eliminati `line_type`, `external_cost`, `external_revenue` e il vincolo `line_shape`; `profile_id` ora è obbligatorio.
- **Sicurezza dei dati**: se esistessero righe esterne "a costo libero" (senza profilo) la migrazione **si ferma con un messaggio** invece di cancellarle. Il rollback ripristina la forma precedente.

## Migrazione `0003` (Step 6)

Campi della coda `email_outbox` per un invio affidabile: `dedupe_key` (chiave unica: una sola email per evento), `next_attempt_at` (ora del prossimo tentativo, per i ritentativi con attesa crescente), `last_attempt_at`, `provider_message_id` (identificativo del messaggio su Mailjet). Le email già in coda risultano subito "da inviare". Vincolo `attempts >= 0`. Vedi [notifiche.md](notifiche.md).

## Migrazione `0004` (practice)

Nuova tabella `practices` (nome unico senza distinzione di maiuscole, `is_active`) e colonna **obbligatoria** `employees.practice_id` (chiave esterna `RESTRICT`: una practice non si elimina, si disattiva).

- **Dati esistenti**: la migrazione crea la practice di sistema **«Da assegnare»** e la assegna a tutti i collaboratori già presenti; solo dopo la colonna diventa `NOT NULL`. L'amministrazione li riassegna dalla scheda *Practice* e dalla scheda del collaboratore (o con l'importazione CSV). È reversibile.
- **Nessun collaboratore senza practice**: un evento del modello assegna «Da assegnare» a ogni collaboratore creato senza indicarne una (API, importazione, script), creando la practice se manca.
- **Practice attuale, senza storico**: il report del carico usa la practice che il collaboratore ha **oggi** per tutti i mesi del periodo; spostare una persona cambia anche i mesi passati.
- **Practice di sistema**: non si rinomina né si disattiva.
- Il nome **«Practice»** esiste già come **profilo** del listino (un livello di seniority): sono concetti diversi.

## Migrazione `0005` (integrazioni)

Accesso da programma a programma con un account di servizio Google (vedi [api.md](api.md)). Nuova tabella `integrations` (email dell'account di servizio unica e minuscola, permessi `create`/`edit`/`read`/`export`, attiva, ultimo utilizzo) e tre colonne sui CE: `integration_id`, `external_ref`, `requested_by`. In più `users.is_service`. Nessun dato esistente cambia; è reversibile.

- **Utente di servizio**: registrare un'integrazione crea un utente (ruolo presale, `is_service`, email uguale a quella dell'account di servizio) che è l'**autore** dei CE creati dal programma esterno. Non può accedere con il login né con un token del portale, e non compare negli elenchi delle persone.
- **Identificativo esterno**: `(integration_id, external_ref)` è unico (indice parziale, solo dove l'identificativo c'è): una richiesta di creazione ripetuta dà lo stesso CE. Non cambia nemmeno se un amministratore assegna poi il CE a un presale (`created_by` cambia, `integration_id` no).
- **Legame con l'account**: `service_account_sub` si imposta alla prima chiamata; se la stessa email torna con un altro identificativo (account ricreato) la chiamata è rifiutata.
- **Limite di una richiesta al secondo**: `last_used_at` si aggiorna con un'istruzione atomica sul database, quindi il limite vale anche con più copie del servizio.

## Migrazione `0006` (business unit)

Le business unit stanno **sopra le practice** (business unit → practice → collaboratori) e, con le consegne successive, decidono chi vede un CE. Nuova tabella `business_units` (nome unico senza distinzione di maiuscole, `is_active`), colonna **obbligatoria** `practices.business_unit_id` (chiave esterna `RESTRICT`), colonna facoltativa `users.business_unit_id` e nuovo ruolo `bu_manager` (responsabile di business unit) nel vincolo `ck_users_role_valid`.

- **Dati esistenti**: la migrazione crea la business unit di sistema **«Da assegnare»** e la assegna a tutte le practice già presenti; solo dopo la colonna diventa `NOT NULL`. Nessun utente cambia.
- **Nessuna practice senza business unit**: un evento del modello assegna «Da assegnare» a ogni practice creata senza indicarne una (API, importazione, script), creandola se manca (come per i collaboratori e la practice).
- **Business unit di sistema**: non si rinomina né si disattiva; **non si assegna a una persona** (serve solo per le practice non ancora assegnate).
- **Persone**: solo presale e responsabili hanno una business unit; per il responsabile è obbligatoria, per il presale facoltativa (serve a migrare). Chi cambia ruolo e non è più presale né responsabile la perde.
- **Collaboratori**: la loro business unit è quella della practice; spostare la practice la cambia, anche per i mesi passati (come per la practice).
- **Disattivare**: una business unit disattivata non si può scegliere per nuove assegnazioni, ma chi la ha già la mantiene.
- **Downgrade**: i responsabili tornano presale, perché il ruolo non esiste più nel vincolo.

## Migrazione `0007` (business unit coinvolte nei CE)

Nuova tabella `ce_business_units` (CE ↔ business unit, chiave composta): le business unit coinvolte valgono per **tutto il CE**, non per la singola versione. Cancellando un CE spariscono le sue righe (`CASCADE`); una business unit usata da un CE non si cancella (`RESTRICT`).

- **Nessuna assegnazione ai CE esistenti nella migrazione**: alla pubblicazione le business unit vere non esistono ancora. L'amministratore le assegna dopo averle create, con **«Assegna ai CE esistenti»** (`POST /api/v1/business-units/apply-to-existing-ces`): dal testo libero della versione e dalle practice dei collaboratori delle righe; idempotente, solo per i CE che non ne hanno, mai «Da assegnare».
- **Testo `ce_versions.business_unit`**: resta, ma **non si compila più**: lo ricava il server dalle business unit coinvolte (nomi in ordine alfabetico separati da « · », al massimo 100 caratteri) e lo usano dashboard, Excel e PDF fino alle consegne successive. Il valore inviato dai client nella testata si ignora.
- **Regole**: almeno una business unit, vera (non «Da assegnare») e attiva (una già coinvolta e poi disattivata si può tenere); si cambiano solo finché l'ultima versione è in bozza o rifiutata (l'admin, solo per un CE che non ne ha nessuna, in qualunque stato); ogni cambio finisce nell'`audit_log` (azione `set_business_units`, con l'elenco di prima e di dopo).
- **Coerenza con le righe**: le business unit dei collaboratori indicati nelle righe (quella della loro practice, esclusa «Da assegnare») devono essere tra quelle coinvolte, altrimenti l'**invio in approvazione è bloccato**; è bloccato anche se il CE non ne ha nessuna.

## Migrazione `0008` (impostazioni del portale)

Nuova tabella `app_settings` (chiave e valore `jsonb`, chi e quando l'ha cambiata) per le impostazioni che l'amministrazione cambia **senza ripubblicare** il servizio. La prima è `bu_visibility_enabled`: **visibilità dei CE per business unit**. Se la chiave manca vale *spenta*, quindi alla pubblicazione nulla cambia.

- **Acceso**: un presale o un responsabile di business unit vede un CE se ne è l'**autore** oppure se la sua business unit è tra quelle coinvolte, e lo vede **per intero** (costi e margini compresi). L'amministratore vede tutto; il viewer e le integrazioni non cambiano. Un presale senza business unit vede solo i propri CE.
- **Un CE che non si vede risponde «CE non trovato»** (404), lo stesso di un CE che non esiste: non si scopre nemmeno che c'è. Il controllo è una dipendenza dei router `/ce` e delle esportazioni, quindi vale per ogni rotta con un `{ce_id}`, anche futura; un test percorre da solo tutte le rotte e un altro fallisce se ne compare una nuova non coperta.
- **Elenco, esportazione dell'elenco, Portfolio**: contano solo i CE visibili. **Carico risorse**: il carico è quello di **tutti** i CE, ma per un presale o un responsabile si mostrano solo le persone (e quindi practice e profili) della propria business unit, senza le righe senza collaboratore e senza codici di CE non visibili; il numero di CE conta solo quelli con righe di quelle persone.
- **Approvazione del responsabile**: approva o rifiuta un CE **in approvazione** che coinvolge la sua business unit (con più business unit basta il responsabile di una qualsiasi); l'amministratore approva sempre. Non dipende dall'interruttore.
- **Rapporto prima di accendere**: CE senza business unit (li vedrebbero solo l'autore e gli amministratori), presale senza business unit, practice attive ancora in «Da assegnare». Si può accendere anche con il rapporto non a zero; ogni cambio dell'interruttore finisce in `audit_log` (entità `setting`).

## Migrazione `0010` (costi vari)

Nuova tabella `ce_extra_costs`, una riga per voce di costi vari di una **versione**: `version_id` (elimina in cascata con la versione), `position`, `description` (300 caratteri), `cost` (`numeric(14,2)`), `markup_pct` (`numeric(7,2)`, predefinito 0; ricarico sul costo). Due vincoli: `ck_ce_extra_costs_cost_non_negative` (costo ≥ 0) e `ck_ce_extra_costs_markup_range` (ricarico tra 0 e 1000). Nessuna riga esiste all'inizio, quindi nessun CE cambia i propri numeri. Le righe sono parte del contenuto della versione: una nuova versione e un duplicato le copiano, una versione approvata non le cambia. Formule e regole: [formule.md](formule.md).

## Migrazione `0009` (esito della trattativa)

Quattro colonne sul **CE** (non sulla versione): `outcome` (`won` = «Close Won», `lost` = «Close Lost», oppure vuoto), `outcome_at`, `outcome_by` e la nota facoltativa `outcome_note`. Due vincoli: il valore è `won` o `lost`; valore, data e autore ci sono **tutti o nessuno** (la nota non esiste senza esito). Il flusso di approvazione e gli stati **non cambiano**; nessun CE ha un esito all'inizio.

- **Quando**: si imposta, cambia o toglie solo se l'**ultima versione è approvata** (`409` altrimenti); lo fanno l'admin, il responsabile di una business unit coinvolta e l'autore del CE. Ogni cambio è nell'`audit_log` (azione `set_outcome`, con valore prima e dopo e nota).
- **Nuova versione**: ammessa dopo Close Won (varianti), **non** dopo Close Lost finché l'esito non viene tolto.
- **Eliminazione**: un CE con esito non si elimina (`409`); le azioni dicono perché (`delete_blocked_reason`) e l'interfaccia lo segnala.
- **Chi lo vede**: chi vede il CE completo vede anche la nota; il **viewer** e le **integrazioni** vedono solo il valore, in sola lettura.
