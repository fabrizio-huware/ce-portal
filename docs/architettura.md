# Architettura

## Panoramica

```
Browser (React, responsive)
        │  HTTPS
        ▼
Cloud Run: frontend ──► Cloud Run: API FastAPI ──► Cloud SQL (PostgreSQL)
                               │
                               ├─► Google Identity (verifica token di login)
                               └─► Mailjet (notifiche email)
```

## Principi
1. **Calcoli solo nel backend.** Il motore di calcolo (giorni lavorativi, % → giorni, costi, ricavi, margini, KPI) è un modulo isolato e testato. Il frontend mostra i risultati e non ricalcola.
2. **Permessi lato server.** Ogni endpoint verifica il ruolo (admin, presale, viewer). Il viewer ha endpoint e schemi di risposta dedicati con i soli dati riassuntivi.
3. **Tariffe congelate.** Alla creazione, il CE copia prezzo e costo giornalieri dei profili: modifiche successive al listino non alterano i CE esistenti.
4. **Versioni immutabili.** Un CE approvato non si modifica: ogni modifica crea una nuova versione.
5. **Predisposizione integrazioni.** Clienti, collaboratori e CE avranno campi per ID esterni (NetSuite, Jira), senza integrazioni attive in questa fase.
6. **Ambienti.** `test` e `prod` in progetti GCP separati, stessa infrastruttura definita da Terraform.
