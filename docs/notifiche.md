# Notifiche email

Le email partono dal portale tramite **Mailjet** (Send API v3.1), con mittente `teamdata@huware.com`.

## Quali email partono

| Evento | Destinatari | Oggetto |
|---|---|---|
| CE inviato in approvazione | tutti gli admin attivi, **escluso chi lo ha inviato** | `[CE] Da approvare: <codice> (v<n>) – <cliente>` |
| CE approvato | l'autore del CE (non se ha approvato lui) | `[CE] Approvato: <codice> (v<n>)` |
| CE rifiutato | l'autore, con il **motivo** | `[CE] Rifiutato: <codice> (v<n>)` |
| Nuova versione creata | tutti gli admin attivi, escluso chi l'ha creata | `[CE] Nuova versione: <codice> (v<n>)` |
| Nuovo utente abilitato | l'utente creato dall'admin | `Accesso al portale Conti Economici` |

- Ogni email ha **un solo destinatario**: nessuno vede gli indirizzi degli altri.
- Non partono email per ritiro, modifica o scarto di una versione, né per i viewer: il viewer non riceve mai nessuna email sui CE.
- Gli utenti **disattivati** non ricevono nulla. Se l'autore del CE è disattivato, l'approvazione procede e l'email non parte.

## Riservatezza
Le email contengono **solo il prezzo**, mai costi o margini: le email sono meno protette del portale. Il resto si legge nel portale tramite il link. I testi inseriti dagli utenti (cliente, progetto, motivo, nomi) sono protetti: nell'HTML non possono introdurre codice, e nell'oggetto gli a-capo vengono eliminati (nessuna iniezione di intestazioni). Il segreto di Mailjet non compare mai in log, errori o risposte delle API.

## Come garantisco che nessuna email si perda
1. L'email viene **registrata nella coda nella stessa transazione** dell'evento. Se l'operazione non riesce (permessi, stato, dati non validi) non nasce nessuna email; se riesce, l'email esiste di sicuro.
2. Subito dopo il salvataggio parte l'**invio immediato** (attesa massima 5 secondi, un'unica chiamata per tutte le email in coda). Se Mailjet non risponde, l'operazione resta valida e l'email rimane in coda.
3. **Ritentativi automatici** con attesa crescente: 1 minuto, 5, 30, 2 ore, 6 ore. Dopo 5 tentativi l'email passa a "fallita" e resta visibile all'admin.
4. **Errori definitivi** (es. indirizzo non valido) falliscono subito, senza insistere.
5. **Errori di configurazione** (credenziali o mittente non validi) non dipendono dall'email: restano in coda e ripartono quando la configurazione è corretta.
6. **Nessun doppione**: ogni email ha una chiave legata all'evento (es. "questo CE, questa revisione, questo destinatario").
7. A ogni nuovo evento vengono riprovate anche le email già in attesa.

## Configurazione

| Variabile | Significato |
|---|---|
| `MAIL_BACKEND` | `auto` (default): in locale le email si scrivono nel log, altrove partono con Mailjet. `console` o `mailjet` per forzare |
| `MAILJET_API_KEY`, `MAILJET_API_SECRET` | credenziali Mailjet. **Mai nel repository né in chat**: in locale in `backend/.env`, in cloud in Secret Manager |
| `MAILJET_SANDBOX` | `true`: Mailjet convalida le email senza consegnarle (utile per la prima verifica) |
| `MAIL_FROM`, `MAIL_FROM_NAME` | mittente (default `teamdata@huware.com`, "Portale Conti Economici") |
| `PUBLIC_BASE_URL` | indirizzo del portale usato nei link (default `http://localhost:5173`) |
| `MAIL_TIMEOUT_SECONDS`, `MAIL_MAX_ATTEMPTS` | attesa massima per chiamata (5) e tentativi prima di "fallita" (5) |

Se le email sono su Mailjet e mancano chiave o segreto, **l'applicazione non parte** con un messaggio chiaro, invece di scoprirlo alla prima email.

## Come verificare Mailjet (dopo averlo configurato)

**Lato Mailjet** (una tantum): crea una chiave API (Account → REST API → API Key Management) e registra e **valida il mittente** `teamdata@huware.com` nella sezione dei mittenti e domini. È consigliata anche l'autenticazione del dominio huware.com (SPF e DKIM). Un mittente non validato produce l'errore `send-0008` di Mailjet: il portale lo riconosce come problema di configurazione e tiene le email in coda.

**Prima verifica, senza consegnare nulla** (modalità sandbox), da `backend/`:
```bash
export MAIL_BACKEND=mailjet MAILJET_SANDBOX=true
export MAILJET_API_KEY=... MAILJET_API_SECRET=...      # solo nel tuo terminale
python -m app.notifications send-test tua.email@huware.com
# OK: email di prova accettata da mailjet (sandbox: non consegnata)
```
**Poi per davvero**: la stessa cosa senza `MAILJET_SANDBOX`. Riceverai "Email di prova – Portale Conti Economici".

> **Attenzione alle variabili esportate.** `export` vale per tutto il terminale finché non lo chiudi. Fai la prova in un terminale dedicato, oppure quando hai finito togli le variabili:
> ```bash
> unset MAIL_BACKEND MAILJET_API_KEY MAILJET_API_SECRET MAILJET_SANDBOX
> ```
> I test ora **ignorano** le variabili d'ambiente e il file `backend/.env` e non possono contattare Mailjet né altri servizi esterni (una chiamata esterna ferma il test). Le chiavi in `backend/.env` (non esportate) sono comunque più sicure, perché valgono solo per l'applicazione.

Oppure dal portale in esecuzione: `POST /api/v1/notifications/test` (solo admin) invia una email di prova a te e restituisce lo stato e l'eventuale errore.

## Gestione (solo admin)

| Operazione | Percorso |
|---|---|
| Elenco delle email con stato, tentativi ed errore (filtri `status`, `type`, `recipient`) | `GET /notifications` |
| Invia subito quelle in coda | `POST /notifications/dispatch` |
| Riprova una email fallita | `POST /notifications/{id}/retry` |
| Email di prova a te stesso | `POST /notifications/test` |

Per capire "perché non è arrivata?": cerca il destinatario nell'elenco. `error` riporta la causa (credenziali, mittente non validato, indirizzo rifiutato, Mailjet non raggiungibile).

## Invio periodico
Quando il portale è "a riposo" su Cloud Run non c'è nessun processo che riprovi le email in attesa. Per questo esiste il comando:
```bash
python -m app.notifications dispatch      # invia le email scadute; esce con codice 1 se qualcuna è fallita
```
Nello **Step 9** lo configuriamo come Cloud Run Job lanciato da Cloud Scheduler ogni 5 minuti. Fino ad allora basta lanciarlo a mano (o usare `POST /notifications/dispatch`); inoltre ogni nuovo evento riprova da solo le email in attesa.

## Come sono collaudate
Il client Mailjet è provato con **chiamate HTTP reali** verso un finto Mailjet locale (`backend/tests/fake_mailjet.py`) che risponde nel formato della Send API v3.1: formato esatto della richiesta (campi, autenticazione Basic, `SandboxMode` alla radice), invio in blocchi da 50 con ordine rispettato, errori per singolo messaggio, errori di credenziali e di mittente, limite di richieste, errori del server, timeout e connessione rifiutata. Da questo ambiente non si può raggiungere Mailjet: la prova con Mailjet vero è il comando `send-test`.
