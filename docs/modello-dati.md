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
    string role "admin | presale | viewer"
    boolean is_active
    string google_sub UK
    timestamp last_login_at
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
  EMPLOYEES {
    uuid id PK
    string first_name
    string last_name
    uuid default_profile_id FK
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
    uuid created_by FK
    timestamp deleted_at
    uuid deleted_by FK
  }
  CE_VERSIONS {
    uuid id PK
    uuid ce_id FK
    int version_number
    string status "draft | submitted | approved | rejected"
    uuid client_id FK
    string project_name
    string sf_opportunity
    string business_unit
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
  }

  PROFILES ||--o{ PROFILE_RATES : "tariffe per anno"
  PROFILES ||--o{ EMPLOYEES : "profilo di default"
  CE ||--|{ CE_VERSIONS : "versioni"
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
