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
