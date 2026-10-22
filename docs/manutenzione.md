# Manutenzione e gestione delle emergenze

Per chi **gestisce** il portale dopo l'avvio. È organizzata per frequenza (cosa fare e quando) e poi per scenario (cosa fare se qualcosa si rompe). Per l'installazione vedi [deploy.md](deploy.md), per le prove [collaudo.md](collaudo.md), per capire com'è fatto [architettura.md](architettura.md).

## Promemoria per frequenza

### Ogni mese (10 minuti)
- [ ] *Amministrazione → Email*: nessuna email **«Fallita»** o ferma «In coda» da giorni. Se ce ne sono, leggi il *Dettaglio* e premi «Riprova».
- [ ] `python3 infra/scripts/check_env.py --project ID --env prod`: nessun ✘; leggi gli ⚠ (in particolare «ultimo backup»).
- [ ] Console Google Cloud → **Fatturazione**: la spesa è nell'ordine che ti aspetti (il budget con avviso deve esistere).
- [ ] Console → Cloud Run → **Log** filtrati per `ERROR`: niente di ricorrente.
- [ ] Rilascio di aggiornamento delle immagini di base (anche senza modifiche al codice): *Actions → Deploy → Run workflow*. Le immagini `python` e `node` ricevono correzioni di sicurezza e il rilascio le include.

### Ogni trimestre (1 ora)
- [ ] **Utenti**: *Amministrazione → Utenti*: disattiva chi non c'è più; controlla chi è admin (devono essere pochi e noti).
- [ ] **Prova di ripristino del database** (R2 di [collaudo.md](collaudo.md)): backup, copia, controllo dei dati, eliminazione della copia. Annota il tempo che ci vuole: è il tuo tempo di ripristino reale.
- [ ] **Dipendenze**: vedi «Aggiornare le librerie» più sotto.
- [ ] Verifica che gli **avvisi** arrivino (R6): notifica di prova al canale.

### Ogni anno (verso novembre-dicembre)
- [ ] **Listino del nuovo anno**: *Amministrazione → Listino → Importa il listino da CSV* con le tariffe dell'anno. **Va fatto prima** che qualcuno crei CE che iniziano in quell'anno: senza listino la creazione si rifiuta con un messaggio chiaro.
- [ ] **Festività**: *Amministrazione → Calendario* → scegli l'anno → «Genera le festività». (Quelle 2026 e 2027 sono già caricate dai dati iniziali; dal 2028 vanno generate.)
- [ ] **Chiusure aziendali** dell'anno: a mano o da CSV (`Data; Descrizione`).
- [ ] **Rotazione dei segreti**: chiave delle sessioni e chiavi di Mailjet (sotto).
- [ ] Rileggi **chi ha accesso** al progetto Google Cloud e al repository GitHub.
- [ ] Controlla la **scadenza e la configurazione** della schermata di consenso OAuth e del Client ID.

### Quando cambia una persona
| Evento | Cosa fare |
|---|---|
| Entra una persona che usa il portale | *Utenti* → «Nuovo utente» con il ruolo giusto (riceve l'email) |
| Entra una persona che compare nei CE | *Collaboratori* → «Nuovo collaboratore» con il profilo di default e la **practice** (sono anagrafiche **separate** dagli utenti) |
| Cambia la practice di una persona | *Collaboratori* → Modifica → Practice. Vale **per tutto il periodo** dei report, anche i mesi passati (non c'è storico) |
| Un programma esterno deve poter creare, leggere o esportare CE | *Integrazioni* → «Nuova integrazione» con l'email del suo account di servizio e i permessi; comunica a chi lo sviluppa l'indirizzo mostrato in alto (audience del token). Per **fermarlo subito**: *Modifica* → disattiva |
| Un CE creato da un programma esterno deve passare a una persona | nel dettaglio del CE, **«Assegna a un presale»** (solo admin). Finché non lo fai, solo gli amministratori possono inviarlo in approvazione e approvarlo |
| Nasce o si chiude un'area (una practice) | *Practice*: crea o disattiva. Prima di disattivare una practice riassegna le persone, altrimenti la mantengono ma non si può più scegliere per altri |
| Dopo aver creato le business unit, i CE vecchi non ne hanno | *Business unit* → **«Assegna ai CE esistenti»** (si può ripetere): le ricava dal testo vecchio e dalle practice dei collaboratori; poi apri i CE che restano senza e scegli tu (l'admin può farlo anche su un CE approvato che non ne ha nessuna) |
| Nasce o si chiude una business unit | *Business unit* → «Nuova business unit» o disattiva; poi assegna le practice (*Practice* → modifica) e le persone (*Utenti* → modifica). «Da assegnare» è di sistema: le practice che ci restano vanno spostate |
| Un presale o un responsabile cambia business unit | *Utenti* → modifica → Business unit. Il responsabile deve sempre averne una |
| Una persona lascia l'azienda | *Utenti* e *Collaboratori*: **disattiva** entrambi. I CE passati restano com'erano. Non si elimina nulla |
| Cambia ruolo | *Utenti* → Modifica → Ruolo (vale dalla prossima richiesta) |
| Cambia l'amministratore di riferimento | prima aggiungi il nuovo admin, poi togli il ruolo al vecchio (l'ultimo admin attivo non si può togliere) |

## Aggiornare le librerie e l'infrastruttura

Le versioni sono **fissate di proposito**: una libreria che esce nuova non cambia nulla finché non la aggiorni tu.

**Backend (Python)**
```bash
make lock           # rigenera backend/requirements.lock e requirements-dev.lock con le ultime versioni
make api-types      # se lo schema dell'API è cambiato, rigenera i tipi del frontend
make test           # tutti i test del backend
make lint
```
Poi commit di `backend/requirements.lock`, `backend/requirements-dev.lock`, `frontend/openapi.json` e `frontend/src/api/schema.d.ts`. Se un test fallisce dopo l'aggiornamento, non forzare: o si corregge il codice o si resta alla versione precedente (una libreria alla volta aiuta a capire quale).

**Frontend (Node)**
```bash
cd frontend
npm outdated
npm update          # oppure una libreria alla volta
npm test && npm run test:e2e
```
Commit di `package.json` e `package-lock.json`.

**Terraform e provider**
```bash
cd infra/terraform/envs/test      # poi prod
terraform init -upgrade
terraform plan                    # deve mostrare pochi o nessun cambiamento
```
Commit di `.terraform.lock.hcl`. Prima sul test, poi sulla produzione. Un `plan` che propone di **distruggere** qualcosa non va applicato: fermati e capisci perché.

**PostgreSQL**: la versione è la 16. Un salto di versione maggiore di Cloud SQL è un'operazione da pianificare (copia, prova, finestra concordata): non si fa con un semplice `apply`.

## Rotazione dei segreti

| Segreto | Come | Effetto |
|---|---|---|
| Chiave delle sessioni (`…-jwt-secret`) | nuova versione del segreto (`gcloud secrets versions add …`), poi nuovo avvio del servizio | tutti devono rifare l'accesso |
| Chiavi di Mailjet | crea nuove chiavi in Mailjet, aggiungile come nuova versione dei due segreti, poi nuovo avvio; disattiva le vecchie | nessun effetto visibile; prova con «Invia un'email di prova» |
| Password del database | da `infra/terraform/envs/<amb>`: `terraform apply -replace=module.ce_portal.random_password.db` (aggiorna password dell'utente del database e segreto), poi **riavvio del servizio e dei lavori** (comando qui sotto, oppure un nuovo rilascio) | breve interruzione fino al riavvio: fallo in una finestra tranquilla, prima sul test |

Il nuovo avvio si forza con `gcloud run services update ce-portal-prod --update-env-vars=RIAVVIO=$(date +%s) --region europe-west8 --project ID-PROD`.

## Emergenze: cosa fare

Regola d'oro: **in dubbio, non cancellare e non sovrascrivere**. Il ripristino dei dati si fa sempre su una **copia**.

| Scenario | Cosa fare |
|---|---|
| **Il portale non risponde** | 1) `python3 infra/scripts/check_env.py …` per vedere cosa è rotto. 2) Log del servizio (console → Cloud Run → Log). 3) Se è dopo un rilascio, **torna alla revisione precedente** (R1). 4) Se il database non è «RUNNABLE», guarda *Cloud SQL* nella console |
| **Un rilascio ha rotto qualcosa** | `gcloud run revisions list --service ce-portal-prod …` e `gcloud run services update-traffic ce-portal-prod --to-revisions=REVISIONE-BUONA=100 …`. Le migrazioni già applicate restano: devono essere compatibili col codice precedente (regola «prima aggiungi, poi usa, poi rimuovi») |
| **Un CE è stato eliminato per errore** | *Amministrazione → CE eliminati* → «Ripristina». Nessun dato perso |
| **Dati cancellati o modificati per errore nel database** | Non ripristinare in fretta sull'istanza viva. Crea una **copia** a un istante precedente (`gcloud sql instances clone ce-portal-prod-db copia-recupero --point-in-time AAAA-MM-GGTHH:MM:SSZ`), controlla i dati nella copia, poi decidi: riportare solo ciò che serve oppure sostituire. Il tempo reale lo conosci dalla prova trimestrale |
| **L'accesso con Google non funziona** | «no registered origin»: l'indirizzo non è tra le *Origini JavaScript autorizzate* del Client ID. «Utente non abilitato»: l'account non è registrato. Client ID cambiato: aggiorna `google_oauth_client_id` e `terraform apply`. Dettagli in [deploy.md](deploy.md), «Se qualcosa non va» |
| **Le email non partono** | *Amministrazione → Email*: leggi l'errore. Chiavi scadute o mittente non convalidato in Mailjet sono le cause tipiche. Controlla che lo scheduler sia attivo (`gcloud scheduler jobs list --location europe-west8`). Dopo la correzione «Riprova» |
| **Un segreto è stato esposto** (chiave sessioni, Mailjet, password database) | ruota subito il segreto (tabella sopra); per la chiave delle sessioni significa far rifare l'accesso a tutti. Poi guarda l'audit log e i log per capire se è stato usato |
| **Un account è stato compromesso** | *Utenti* → disattivalo subito (perde l'accesso alla prossima richiesta); controlla *Storico* dei CE che ha toccato; reimposta le credenziali Google dell'account |
| **L'account GitHub o un token è compromesso** | la pubblicazione usa identità temporanee limitate al repository, quindi non ci sono chiavi da revocare; revoca l'accesso della persona e controlla gli ultimi rilasci e le approvazioni dell'Environment `production` |
| **La spesa è salita all'improvviso** | Fatturazione → Report per servizio. Cause tipiche: istanza database più grande o alta disponibilità attivata, `min_instances` troppo alto, errori in ciclo che fanno ripartire i lavori |
| **La regione non è disponibile** | il portale è in una sola regione: si aspetta il ripristino da parte di Google, oppure si ricostruisce in un'altra regione da backup (non automatico: va pianificato prima se il rischio non è accettabile) |
| **Il disco del database si riempie** | è impostato per crescere da solo; se succede, guarda *Cloud SQL → Utilizzo* e cerca ciò che cresce (tabella `audit_log` o `email_outbox`) |

## Cosa resta aperto

Non sono difetti: sono scelte rimandate o cose da decidere. Le teniamo qui perché non si perdano.

| Tema | Stato |
|---|---|
| **Logo in vettoriale** | il logo è un PNG a 410 px (`frontend/public/brand`, e `backend/app/assets` per i PDF, nero e bianco); con un SVG sarebbe nitido a ogni dimensione. Se cambi il logo, aggiorna entrambe le versioni |
| **Font dei PDF** | DM Sans è incorporato (`backend/app/assets/fonts`, licenza OFL nella stessa cartella): non cancellare `OFL.txt`. Se il marchio adotta un altro font va cambiato lì |
| **Font** | è usato **DM Sans**, identificato per confronto visivo con huware.com: da confermare con chi cura il marchio |
| **Chiusure aziendali 2026-2027** | non ancora fornite: vanno inserite da *Calendario* (a mano o da CSV) |
| **Dominio proprio** | si usa l'indirizzo `run.app`; per un dominio proprio serve collegarlo (bilanciatore o mappatura, a seconda della regione): vedi [deploy.md](deploy.md) |
| **Scelta del cliente con molti clienti** | l'elenco offerto nelle scelte e nei filtri mostra i primi **200 clienti** in ordine alfabetico (limite dell'API). Va bene finché i clienti sono meno; oltre servirebbe una ricerca mentre si digita |
| **Barra dei totali attenuata durante il ricalcolo** | per circa mezzo secondo, mentre i totali si aggiornano, la barra è volutamente attenuata (`opacity-60`) e le sue etichette piccole scendono sotto il contrasto AA. È un comportamento transitorio già presente; i controlli di accessibilità aspettano che si stabilizzi. Da valutare se serve un altro segnale (per esempio un'icona) senza ridurre il contrasto |
| **Storico delle practice** | la practice è quella attuale per tutto il periodo: spostare una persona cambia anche i mesi passati. Se servisse, si può aggiungere una practice con data di inizio |
| **Nome «Practice»** | esiste anche come **profilo** del listino (un livello di seniority): sono concetti diversi e nelle schermate si possono confondere. Valutare se rinominare uno dei due |
| **Elenco delle integrazioni** | mostra anche quelle disattivate, in ordine alfabetico, e non si eliminano: con il tempo può servire un filtro «solo attive» |
| **Elenco delle business unit** | mostra anche quelle disattivate, in ordine alfabetico, e non si eliminano: può servire un filtro «solo attive» |
| **Business unit: consegne 3–5** | la visibilità per business unit, l'approvazione del responsabile e le dashboard per business unit non sono ancora attive: finora esistono l'anagrafica, la gerarchia, il ruolo e le business unit dichiarate nei CE |
| **Elenco delle practice** | mostra anche quelle disattivate, in ordine alfabetico: con il tempo può servire un filtro «solo attive» |
| **Salvataggio automatico** dell'editor | oggi è manuale, con avvisi: da valutare se serve |
| **Consultazione dell'audit log** nell'interfaccia | il server registra tutto, ma non c'è una schermata |
| **Limite alle richieste** (rate limiting) e accesso con IAP/VPN | non inclusi: da valutare in base al rischio |
| **Aggiornamenti automatici delle dipendenze** | non attivati (Dependabot o simili); oggi sono manuali, trimestrali |
| **Integrazioni Jira e NetSuite** | i campi per gli ID esistono, nessuna integrazione attiva |
| **Fuori ambito dall'analisi** | override delle tariffe per riga, Fondi/PSF, campi Monday/Partners/EST |
| **Più regioni** | non previsto; vedi l'emergenza «regione non disponibile» |
