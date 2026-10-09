# Pubblicazione su Google Cloud

> **Stato**: tutto il necessario è pronto (immagine, infrastruttura, pubblicazione automatica), ma **non è mai stato eseguito su un vero progetto Google Cloud**. Le verifiche fatte e quelle che restano sono nella sezione [«Cosa è stato verificato»](#cosa-è-stato-verificato-e-cosa-no). Leggila prima di mettere in linea qualcosa.

## Cosa si costruisce

Per **ciascun ambiente** (test e produzione, in due progetti Google Cloud separati):

| Pezzo | A cosa serve |
|---|---|
| **Servizio Cloud Run** `ce-portal-<ambiente>` | un'unica applicazione: API e frontend insieme (immagine unica, stessa per test e produzione) |
| **Cloud SQL** PostgreSQL 16 | il database, con backup giornalieri; solo connessioni cifrate, raggiungibile solo dal servizio |
| **Artifact Registry** | le immagini (si tengono le ultime 20 e quelle più recenti di 30 giorni) |
| **Secret Manager** | 4 segreti: chiave delle sessioni, password del database (generati da Terraform) e le due chiavi di Mailjet (le metti tu) |
| **3 lavori Cloud Run** | `migrate` (aggiorna il database), `seed` (listino e festività iniziali, una sola volta), `mail` (invia le email in coda) |
| **Cloud Scheduler** | lancia il lavoro `mail` ogni 5 minuti: recupera le email fallite e quelle rimaste in coda |
| **Avvisi** | controllo di raggiungibilità ogni 5 minuti; avvisi per errori 5xx e lavori falliti, per email |
| **GitHub senza chiavi** | GitHub Actions ottiene un'identità temporanea (Workload Identity Federation): nessun file di chiavi da custodire, e solo il tuo repository può usarla |

```
 GitHub (main) ──CI──► build immagine ──► registro test ─► servizio test ─┐
                                      └─► registro prod        (approvazione) ─► servizio prod
 browser ──https──► Cloud Run (API + frontend) ──socket──► Cloud SQL
                          ▲ segreti da Secret Manager
 Cloud Scheduler ──ogni 5′──► lavoro «mail» ──► Mailjet
```

**Perché un solo servizio**: il backend serve anche i file del frontend. Niente CORS, niente secondo servizio da pubblicare e tenere allineato. La stessa immagine funziona in ogni ambiente: ciò che cambia (Client ID di Google, database, indirizzi) arriva a runtime dalla configurazione, e il frontend lo legge da `/api/v1/config`.

## Cosa serve prima di iniziare

| Cosa | Dove si ottiene |
|---|---|
| Due progetti Google Cloud (test e produzione) con la **fatturazione attiva** | console Google Cloud → «Nuovo progetto», poi Fatturazione |
| Un account con ruolo **Proprietario** sui progetti (solo per la prima installazione) | il tuo account amministratore Google Cloud |
| `gcloud` ([installazione](https://cloud.google.com/sdk/docs/install)) e `terraform` ≥ 1.6 (o OpenTofu) sul tuo computer | — |
| Il repository GitHub (`organizzazione/repository`) | GitHub |
| Un **Client ID OAuth di Google** per l'accesso | vedi sotto |
| Un account **Mailjet** con il mittente `teamdata@huware.com` convalidato | Mailjet → Sender & Domains |
| Un indirizzo email per gli **avvisi** | per esempio teamdata@huware.com |

**Come si crea il Client ID di Google** (per ogni ambiente, o uno solo se preferisci): console → *API e servizi* → *Schermata consenso OAuth* (tipo «Interno» se usi Google Workspace: ammette solo gli account dell'organizzazione) → *Credenziali* → *Crea credenziali* → *ID client OAuth* → *Applicazione web*. In *Origini JavaScript autorizzate* metti l'indirizzo del portale (lo conosci dopo il primo `terraform apply`: è l'output `service_url`). Non servono «URI di reindirizzamento». Il Client ID **non è segreto**; il «client secret» **non serve**.

## Prima installazione (ambiente di test)

Fai prima il test, poi la produzione con gli stessi passi.

1. **Prepara il progetto** (una sola volta per progetto): abilita le API di base e crea il bucket dello stato di Terraform.
   ```bash
   gcloud auth login
   infra/scripts/bootstrap-project.sh ID-DEL-PROGETTO-TEST
   ```
2. **Compila i valori e crea l'infrastruttura.**
   ```bash
   cd infra/terraform/envs/test
   cp backend.hcl.example backend.hcl            # controlla il nome del bucket
   cp terraform.tfvars.example terraform.tfvars  # inserisci progetto, repository GitHub, email
   terraform init -backend-config=backend.hcl
   terraform plan                                # leggilo: deve creare risorse, non eliminarne
   terraform apply
   ```
   Se l'organizzazione vieta l'accesso a `allUsers`, prima di partire aggiungi a `terraform.tfvars` la riga `public_access_method = "disable_iam_check"` (vedi «Se qualcosa non va»).
   Il primo `apply` richiede alcuni minuti (soprattutto Cloud SQL). Se segnala «API not enabled», aspetta un minuto e ripeti il comando. Il servizio parte con un'immagine di esempio di Google: è normale, la sostituirà il primo rilascio.
3. **Annota gli output** (`terraform output`): `service_url`, `workload_identity_provider`, `deploy_service_account`.
4. **Client ID di Google**: crealo come spiegato sopra con `service_url` come origine autorizzata, scrivilo in `terraform.tfvars` (`google_oauth_client_id`) e rilancia `terraform apply` (cambia solo una variabile del servizio).
5. **Chiavi di Mailjet** (non passano da Terraform: finirebbero nello stato). Inseriscile senza che restino nella cronologia della shell:
   ```bash
   read -rs KEY    && printf '%s' "$KEY"    | gcloud secrets versions add ce-portal-test-mailjet-api-key    --data-file=- --project ID-DEL-PROGETTO-TEST
   read -rs SECRET && printf '%s' "$SECRET" | gcloud secrets versions add ce-portal-test-mailjet-api-secret --data-file=- --project ID-DEL-PROGETTO-TEST
   ```
   (Se vuoi partire senza email vere: in `terraform.tfvars` metti `mail_backend = "console"`; le email si scrivono solo nel log.) Il servizio legge sempre l'ultima versione al prossimo avvio: dopo aver cambiato un segreto pubblica di nuovo (o `gcloud run services update … --update-env-vars=RIAVVIO=$(date +%s)`).
6. **Configura GitHub** (Impostazioni del repository):
   - *Environments*: crea `test` e `production`. In `production` attiva **Required reviewers** (chi deve approvare ogni rilascio in produzione).
   - *Secrets and variables → Actions → Variables*: `GCP_REGION` (`europe-west8`), `TEST_GCP_PROJECT`, `TEST_WORKLOAD_IDENTITY_PROVIDER`, `TEST_DEPLOY_SERVICE_ACCOUNT` (dagli output del test) e le tre `PROD_…` corrispondenti (dagli output di produzione). Sono identificativi, non segreti.
7. **Primo rilascio**: un push su `main` lancia la CI e, se passa, il workflow *Deploy*: costruisce l'immagine, la prova, la pubblica, esegue le migrazioni e aggiorna il servizio di test. Per lanciarlo a mano: *Actions → Deploy → Run workflow*.
8. **Dati iniziali** (una sola volta per ambiente: 9 profili del listino 2026, festività 2026-2027, amministratore iniziale):
   ```bash
   gcloud run jobs execute ce-portal-test-seed --region europe-west8 --project ID-DEL-PROGETTO-TEST --wait
   ```
9. **Apri `service_url`** e accedi con Google usando l'email di `bootstrap_admin_email`. Poi, da *Amministrazione*: aggiungi gli utenti, importa i collaboratori, aggiorna il listino e le chiusure aziendali.

## Produzione

Stessi passi, in `infra/terraform/envs/prod` e col progetto di produzione. Differenze già impostate: database più capiente (`db-custom-1-3840`), recupero a un istante preciso attivo, 14 giorni di backup, **protezione dall'eliminazione** su database e servizi, Cloud Run fino a 5 istanze.

Decisioni tue, modificabili in `envs/prod/main.tf`:
- `min_instances`: `0` = il servizio si spegne quando non serve (il primo accesso dopo una pausa impiega qualche secondo); `1` = sempre pronto, con un costo fisso in più.
- `db_availability_type`: `ZONAL` (predefinito) oppure `REGIONAL` (alta disponibilità, costa circa il doppio per il database).

## Il rilascio di tutti i giorni

1. Si unisce una modifica a `main` → parte la **CI** (test backend, frontend, browser, immagine).
2. Se la CI passa → **Deploy**: costruisce l'immagine **una volta**, la prova (`smoke.sh`) e la pubblica nei registri di test e produzione con la stessa etichetta (le prime 12 cifre del commit).
3. **Test**: aggiorna i lavori, esegue le migrazioni, pubblica il servizio, fa i controlli di fumo. Se falliscono, il traffico torna alla revisione precedente.
4. **Produzione**: parte solo dopo l'**approvazione** di chi hai indicato in GitHub. Stessi passi, con controlli più severi (HSTS, nessun accesso simulato, documentazione dell'API spenta).

**Regola per le migrazioni del database**: vengono applicate *prima* del codice nuovo e non si annullano da sole se si torna indietro. Per questo ogni migrazione deve funzionare anche con il codice precedente: prima si **aggiunge** (colonna nuova, facoltativa), in un rilascio successivo si **usa**, e solo dopo si **rimuove** ciò che non serve più.

**Tornare indietro a mano**:
```bash
gcloud run revisions list --service ce-portal-prod --region europe-west8 --project ID-PROD
gcloud run services update-traffic ce-portal-prod --to-revisions=NOME-REVISIONE=100 --region europe-west8 --project ID-PROD
```

## Operazioni

| Cosa | Come |
|---|---|
| Vedere i log | console → Cloud Run → servizio → *Log*; oppure `gcloud run services logs read ce-portal-prod --region europe-west8 --project ID-PROD`. I log sono in JSON con la gravità, quindi Cloud Logging li filtra per livello |
| Vedere le email inviate | nel portale: *Amministrazione → Email* (stato, tentativi, errore; «Riprova» per le fallite) |
| Inviare subito le email in coda | *Amministrazione → Email → Invia subito*, oppure `gcloud run jobs execute ce-portal-prod-mail --region … --wait` |
| Backup del database | automatici ogni notte; `gcloud sql backups list --instance ce-portal-prod-db --project ID-PROD`. Un backup manuale: `gcloud sql backups create --instance ce-portal-prod-db` |
| **Ripristinare il database** | non sovrascrivere in fretta: crea prima una copia (`gcloud sql instances clone ce-portal-prod-db ce-portal-prod-db-recupero --point-in-time 2026-10-07T10:00:00Z`), controlla i dati, e solo dopo decidi. Con la protezione attiva Terraform non elimina nulla |
| Cambiare la chiave delle sessioni | nuova versione del segreto `ce-portal-<amb>-jwt-secret`, poi nuovo avvio del servizio: tutti dovranno rifare l'accesso |
| Ruotare le chiavi di Mailjet | nuova versione dei due segreti (comandi del passo 5) e nuovo avvio |
| Cambiare dimensioni o istanze | variabili in `envs/<amb>/main.tf` e `terraform apply` |
| Aggiungere un amministratore | dal portale: *Amministrazione → Utenti* (non serve toccare l'infrastruttura) |
| Dipendenze Python | cambia `backend/pyproject.toml`, poi `make lock` e fai commit di `backend/requirements.lock` (la CI ne controlla la coerenza) |

**Dominio proprio**: imposta `public_url_override = "https://ce.example.com"` e `terraform apply` (aggiorna i link nelle email), poi aggiungi il dominio tra le *Origini JavaScript autorizzate* del Client ID. Il collegamento del dominio a Cloud Run **non è incluso**: la «mappatura dei domini» di Cloud Run non è disponibile in tutte le regioni (verifica che lo sia per `europe-west8`), l'alternativa è un bilanciatore di carico con certificato gestito.

**Costi**: la voce principale è **Cloud SQL** (è sempre acceso); Cloud Run, Artifact Registry, Secret Manager e Scheduler a questo volume pesano pochissimo. Non riporto cifre perché i prezzi cambiano: stimale con il [calcolatore di Google Cloud](https://cloud.google.com/products/calculator) inserendo la taglia scelta (`db_tier`), la regione, il disco e la scelta ZONAL/REGIONAL. Imposta anche un **budget con avviso** nella console (Fatturazione → Budget e avvisi).

## Sicurezza: cosa c'è e cosa resta a te

**Già impostato**: solo HTTPS con HSTS; regole di sicurezza del browser (CSP che ammette solo il portale e l'accesso Google, niente incorporamento in altri siti, niente MIME sniffing); risposte dell'API mai in cache condivise; documentazione interattiva dell'API spenta in produzione; accesso simulato inesistente fuori da `local`; chiave delle sessioni e password del database generate (non scelte da una persona); database senza reti autorizzate e solo connessioni cifrate; segreti in Secret Manager, letti solo dall'account di esecuzione; permessi minimi per l'account che pubblica; GitHub senza chiavi, limitato al tuo repository; protezione dall'eliminazione e backup su produzione; il contenitore non gira come amministratore.

**Da decidere o non incluso**:
- Il servizio è raggiungibile da Internet, con `allUsers` oppure con il controllo IAM disattivato (la pagina di login la può aprire chiunque; entra solo chi è registrato e ha un dominio ammesso). Per restringerlo serve altro (Identity-Aware Proxy, VPN o ingresso interno): impostando `allow_unauthenticated = false` il servizio non è più pubblico, ma il portale così non si apre dai browser senza un livello davanti.
- Non c'è un limite al numero di richieste (rate limiting) oltre a quello naturale di Cloud Run.
- Il Client ID e la schermata di consenso OAuth si creano a mano.

## Se qualcosa non va

| Sintomo | Causa probabile e cosa fare |
|---|---|
| `terraform apply` fallisce con **«One or more users named in the policy do not belong to a permitted customer»** (o «…organization policy») sul permesso del servizio | l'organizzazione ha la policy **«Condivisione ristretta ai domini»** (`iam.allowedPolicyMemberDomains`) e vieta di dare accesso a `allUsers`. **Soluzione senza toccare la policy**: in `terraform.tfvars` aggiungi `public_access_method = "disable_iam_check"` e rilancia `terraform apply` (il servizio è già stato creato: si aggiorna soltanto). Disattiva il controllo di invocazione IAM di Cloud Run: il servizio resta pubblico e protetto dal login dell'applicazione. In alternativa un amministratore dell'organizzazione può concedere un'eccezione alla policy per il solo progetto (console → IAM e amministrazione → Policy dell'organizzazione). Se vuoi che il servizio **non** sia pubblico: `allow_unauthenticated = false` (serve un livello davanti, per esempio Identity-Aware Proxy) |
| Aprendo il portale vedi la pagina «Hello» di Google | il primo rilascio non è ancora avvenuto: lancia il workflow *Deploy* |
| Accesso: **«Utente non abilitato»** | l'email non è registrata. L'amministratore iniziale si crea all'avvio solo se `bootstrap_admin_email` è impostata **e** il database non ha utenti; altrimenti aggiungilo da un altro admin |
| Pulsante Google assente o errore `origin_mismatch` | `google_oauth_client_id` vuoto, oppure l'indirizzo non è tra le *Origini JavaScript autorizzate* del Client ID (vanno scritte esattamente, con `https://`) |
| La CI è verde ma *Deploy* si ferma alle migrazioni | guarda i log del lavoro `…-migrate` (Cloud Run → Lavori → Esecuzioni). Cause tipiche: password o istanza errate, permesso `cloudsql.client` mancante, errore nella migrazione |
| Il servizio non parte (revisione non pronta) | log della revisione: spesso un segreto mancante o `JWT_SECRET`/chiavi Mailjet vuote con `mail_backend = "mailjet"` |
| Errori di connessione al database | l'istanza non è accesa, oppure `CLOUDSQL_INSTANCE`/`DB_USER` non corrispondono (sono impostati da Terraform: non cambiarli a mano) |
| Le email restano «in coda» o «fallite» | chiavi di Mailjet ancora «DA-IMPOSTARE», mittente non convalidato in Mailjet, oppure Mailjet in modalità prova. *Amministrazione → Email* mostra l'errore esatto |
| Lo scheduler non invia | `gcloud scheduler jobs list --location europe-west8`: deve essere abilitato, e `…-mail` deve avere il permesso `run.invoker` per l'account di pianificazione (lo crea Terraform) |
| `terraform apply` dà «already exists» | una risorsa creata a mano con lo stesso nome: importala (`terraform import`) o rinominala |
| `terraform apply` per Cloud Run chiede di scegliere l'immagine | mai: l'immagine è ignorata dopo la creazione. Se succede, hai cambiato `ignore_changes` |

## Smantellare un ambiente

`deletion_protection` impedisce di eliminare per errore. Per eliminare davvero: imposta `deletion_protection = false` nell'ambiente, `terraform apply`, poi `terraform destroy`. **Il database con i suoi backup andrà perso.** Il bucket dello stato (`<progetto>-tfstate`) e le API abilitate restano: si eliminano a mano.

## Cosa è stato verificato (e cosa no)

**Verificato in locale, senza Google Cloud:**
- il backend in modalità produzione (`APP_ENV=prod`) servito come farà il contenitore: pagine dell'applicazione, risorse con cache lunga, intestazioni di sicurezza, documentazione dell'API spenta, assenza dell'accesso simulato, log in JSON, avvio con 0 errori;
- i tre lavori (migrazioni, dati iniziali, email) eseguiti con il loro comando, e il seed ripetuto due volte senza danni;
- un browser vero sulla pagina di accesso: nessuna violazione delle regole di sicurezza, font e stili caricati;
- la composizione dell'indirizzo di Cloud SQL (anche con password con caratteri speciali);
- `Dockerfile` (hadolint senza avvisi), flussi GitHub Actions (actionlint senza avvisi), script (shellcheck senza avvisi);
- Terraform (con OpenTofu): formato, validità di modulo e ambienti rispetto agli schemi reali dei provider, e **19 test** con provider simulati su valori, permessi e protezioni.

**NON verificato — da controllare al primo uso reale:**
- **l'immagine non è mai stata costruita con Docker** (qui non c'è Docker): i passi sono stati eseguiti a mano uno per uno, ma la prima `docker build` può rivelare un dettaglio. La CI la costruisce a ogni modifica;
- **nessun `terraform plan` o `apply` contro Google Cloud**: lo schema è valido e i valori sono quelli attesi, ma i permessi reali, le quote e i limiti delle regioni (per esempio la disponibilità di Cloud SQL o dei domini in `europe-west8`) emergono solo lì;
- l'accesso con Google vero (script `accounts.google.com/gsi/client` e relative regole di sicurezza): da qui non raggiungo Google. Se il pulsante non compare, guarda la console del browser: un'eventuale regola da aggiungere è in `backend/app/security.py`;
- Cloud SQL via socket da Cloud Run, Cloud Scheduler che lancia il lavoro, le chiamate di `gcloud` nei flussi, il rilascio con approvazione e il ripristino automatico;
- l'invio con Mailjet vero.

Per questo conviene che il **primo giro** sia sul progetto di **test**, con calma, con questa guida davanti.

## Appendice: variabili d'ambiente del backend

Le imposta Terraform su Cloud Run (tranne dove indicato); in locale stanno in `backend/.env`.

| Variabile | Significato |
|---|---|
| `APP_ENV` | `local`, `test` o `prod`. Fuori da `local` servono una chiave delle sessioni vera e, con Mailjet, le sue chiavi; l'accesso simulato non esiste |
| `DATABASE_URL` | indirizzo del database (sviluppo) |
| `CLOUDSQL_INSTANCE`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` | database Cloud SQL via socket: `progetto:regione:istanza`, utente, password (da Secret Manager), nome. Hanno la precedenza su `DATABASE_URL` |
| `STATIC_DIR` | cartella del frontend compilato (nell'immagine: `/app/static`); se indicata il backend serve anche il frontend |
| `JWT_SECRET` | chiave delle sessioni (da Secret Manager), almeno 32 caratteri fuori da `local` |
| `GOOGLE_OAUTH_CLIENT_ID`, `ALLOWED_EMAIL_DOMAINS`, `BOOTSTRAP_ADMIN_EMAIL` | accesso con Google, domini ammessi, primo amministratore |
| `MAIL_BACKEND`, `MAILJET_API_KEY`, `MAILJET_API_SECRET`, `MAIL_FROM`, `PUBLIC_BASE_URL` | email (`mailjet` o `console`), chiavi (da Secret Manager), mittente, indirizzo del portale usato nei link |
| `CORS_ORIGINS` | origini ammesse; con un solo servizio coincide con l'indirizzo del portale |
