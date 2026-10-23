# Registro delle modifiche

Qui sono registrate **tutte le richieste di modifica e di nuove funzionalità** fatte per il portale, dalla più recente alla più vecchia: cosa è stato chiesto, cosa è stato deciso, cosa è cambiato, come è stato verificato e a che punto è. Serve a non ricostruire a memoria la storia del progetto e a sapere, per ogni cambiamento, **da dove viene**.

**Come si aggiorna** (regola del progetto): a **ogni** richiesta, anche piccola, si apre una voce (stato «In corso») quando il piano è concordato, e la si chiude alla consegna (stato «Consegnata», verifiche, commit). Quando l'utente conferma che una modifica è sul test o in produzione, si aggiorna lo stato. Il file va incluso tra quelli consegnati insieme alle modifiche. `test_changelog.py` controlla il formato.

## Formato di una voce

```
### CL-NNN · AAAA-MM-GG · Titolo
- **Richiesta**: cosa ha chiesto l'utente (sue parole, se brevi, altrimenti sintesi)
- **Tipo**: Funzione | Ritocco | Correzione | Infrastruttura | Documentazione | Strumenti
- **Cosa è cambiato**: ...
- **Decisioni**: scelte fatte con l'utente e perché (facoltativa)
- **Verifica**: cosa è stato provato e cosa no
- **Stato**: In corso | Consegnata | Pubblicata sul test | In produzione | Annullata
- **Commit**: hash nel repository di riferimento, oppure «questo commit» (facoltativo)
```

**Come ritrovare una modifica nel proprio repository**: gli hash della voce «Commit» sono quelli del repository con cui si preparano le consegne e **possono non coincidere** con quelli del repository GitHub, dove i commit li fa l'utente. Per questo, nel messaggio di commit si scrive l'ID della voce (`Refs: CL-029`) e poi si cerca con `git log --grep CL-029`. Le istruzioni di consegna propongono il messaggio.

Le date sono quelle dei commit. Lo stato «Pubblicata sul test» è usato solo per ciò che deve essere in linea perché il test funzioni come l'utente ha riferito («al momento funziona tutto in ambiente di test»); per le altre voci lo stato è «Consegnata». Nessuna voce è «In produzione», perché non è stato confermato.

---

### CL-039 · 2026-10-22 · Business unit sopra le practice, business unit nei CE e visibilità per business unit
- **Richiesta**: gestire diverse business unit sopra le practice; alla creazione di un CE dichiarare quali sono coinvolte; i presale devono vedere tutti i CE in cui la propria business unit è coinvolta.
- **Tipo**: Funzione
- **Cosa è cambiato**: *tutte le 5 consegne completate (anagrafica e gerarchia; business unit nei CE; visibilità e approvazione del responsabile; dashboard e filtri; rifinitura della documentazione).* **Consegna 5:** aggiornati analisi funzionale (ruolo, entità, sezione «Business unit e visibilità», fuori ambito), architettura (principio 10: la visibilità si impone a monte; numeri dei test), collaudo (quattro ruoli e nuova sezione I con 11 prove sulle business unit, la visibilità e l'approvazione del responsabile), dashboard (filtri, sezione e colonne), guida utente, API, frontend e manutenzione; pagina di presentazione tecnica rigenerata dal repository. **Consegna 4:** filtro «Business unit» nell'elenco dei CE e nella sua esportazione (i CE che la coinvolgono) e nel Portfolio (menu al posto del testo libero); l'elenco di un presale o di un responsabile si apre sulla **propria** business unit («Tutte» e «Solo i miei CE» la tolgono); Carico risorse con la sezione «Impegno per business unit», il filtro e la business unit sulle righe delle practice e dei collaboratori, con il perimetro della visibilità (un presale non guarda un'altra business unit); esportazioni con il foglio «Business unit» e la colonna nuova in coda. **Consegna 3:** interruttore «visibilità per business unit» (tabella `app_settings`, migrazione `0008`), **spento alla pubblicazione**, con il rapporto di ciò che manca prima di accendere (CE senza business unit, presale senza business unit, practice in «Da assegnare») e la conferma; acceso, un presale o un responsabile vede un CE se la sua business unit è coinvolta o se ne è l'autore, per intero, e un CE che non vede risponde «CE non trovato» su **ogni** rotta con un identificativo di CE (controllo a monte sui router dei CE e delle esportazioni, quindi non si può dimenticare una rotta); elenco, sua esportazione e Portfolio contano solo i CE visibili; il Carico risorse mostra solo le persone della propria business unit con il carico di tutti i CE; il responsabile di business unit approva e rifiuta un CE in approvazione che coinvolge la sua business unit (admin sempre); viewer e integrazioni invariati. **Consegna 2:** tabella `ce_business_units` (migrazione `0007`); le business unit coinvolte si dichiarano alla creazione (almeno una, vere e attive) e valgono per tutto il CE; `PUT /ce/{id}/business-units` per autore e amministratore in bozza o rifiutato, con registro «da A a B» (l'admin può riparare un CE senza business unit in qualunque stato); l'editor segnala i collaboratori di business unit non coinvolte con «Aggiungi» e l'**invio in approvazione è bloccato** finché non coincidono (e senza business unit); scelta nella creazione e nell'editor, nomi nel dettaglio, nell'elenco e nello storico; la duplicazione le copia; le integrazioni devono indicarle alla creazione (nuovo elenco `/anagrafiche/business-unit`); pulsante «Assegna ai CE esistenti» (`POST /business-units/apply-to-existing-ces`, idempotente). Il testo libero «business unit» non si compila più: lo ricava il server (per dashboard, Excel e PDF). **Cambiamento incompatibile:** `POST /ce` e la creazione delle integrazioni richiedono `business_unit_ids`. Corretto in corsa un difetto dell'interfaccia: le etichette più lunghe facevano sforare di 10 pixel una dashboard (la tabella nascosta per gli screen reader sotto i grafici). **Consegna 1:** nuova anagrafica `business_units` (migrazione `0006`) con la business unit di sistema «Da assegnare»; ogni practice sta in una business unit (obbligatoria) e i collaboratori la ereditano; ogni presale può averne una e il nuovo ruolo **responsabile di business unit** (`bu_manager`, come un presale per ora) deve averla; nuova scheda «Business unit» in Amministrazione, business unit nei moduli e negli elenchi di practice, utenti e collaboratori; dati demo con tre business unit. **Non cambia ancora ciò che si vede:** i presale vedono tutti i CE e il responsabile non approva.
- **Decisioni**: gerarchia business unit → practice (ogni practice in una sola business unit) → collaboratori; business unit di sistema «Da assegnare» per i dati esistenti; un presale appartiene a **una** business unit. Le business unit coinvolte si **dichiarano** alla creazione (almeno una), valgono per **tutto il CE** e le modificano autore e amministratore finché è bozza o rifiutato, con registro delle modifiche; l'editor segnala le incoerenze con i collaboratori delle righe e l'invio in approvazione è **bloccato** finché non coincidono; il testo libero «business unit» di oggi si sostituisce con la scelta strutturata. Un presale vede un CE se la sua business unit è coinvolta **oppure** se ne è l'autore, e lo vede **per intero** (costi e margini compresi); modifica solo i propri. Viewer, integrazioni in lettura e notifiche **invariati**; le integrazioni devono però indicare le business unit quando creano un CE. Nuovo ruolo **responsabile di business unit**: come un presale, e in più approva e rifiuta i CE che coinvolgono la sua business unit (con più business unit basta un amministratore o il responsabile di una qualsiasi di quelle coinvolte). Dashboard: Portfolio sui CE visibili; Carico risorse con sezione e filtro per business unit, e per il presale solo persone e practice della sua business unit con il carico calcolato su tutti i CE (solo giornate aggregate). Passaggio sicuro: interruttore «visibilità per business unit», spento al rilascio, con il rapporto di ciò che manca prima di accenderlo; i CE esistenti ricevono le business unit dal testo libero e dalle practice dei collaboratori, gli altri restano visibili solo ad autore e amministratori.
- **Verifica**: *consegna 5:* test dei documenti (collegamenti e percorsi) verdi; i numeri citati nei documenti sono quelli delle suite (backend 1352, frontend 253). *Consegna 4:* backend 1352 test (nuovi: 8 sui filtri, la sezione, il perimetro e le esportazioni; 4 esistenti aggiornati per il foglio e la colonna in più); frontend 253 test unitari, tipi e compilazione; nel browser dashboard, visibilità, elenco, editor, dettaglio, accessibilità, accesso e layout su desktop e smartphone; 17 prove «al contrario» (10 backend, 4 sulle funzioni, 3 nel browser), tutte individuate: una prova nel browser era passata a vuoto perché l'errore inserito non compilava e restava servito il codice vecchio, ripetuta con un errore che compila. *Consegna 3:* backend 1344 test (nuovi: 18 sulla visibilità, tra cui uno che percorre da solo ogni rotta con un identificativo di CE e uno che fallisce se ne compare una nuova non coperta; 1 sulle integrazioni, che non cambiano; righe nuove nelle due matrici dei permessi; 1 sulla migrazione); frontend 249 test unitari, tipi e compilazione; nel browser 4 prove sulla visibilità (elenco, dettaglio, responsabile che approva, responsabile di un'altra business unit) e le altre su desktop e smartphone; 24 prove «al contrario» (17 backend, 4 sulle funzioni, 3 nel browser), tutte individuate. *Consegna 2:* backend 1303 test (nuovi: 16 sul CE e sulle business unit, 3 sul contratto delle integrazioni, 1 sulla migrazione; 330 test esistenti aggiornati dagli aiutanti condivisi e 9 a mano); frontend 244 test unitari, tipi e compilazione; nel browser creazione, editor, elenco e amministrazione, accessibilità, dashboard, dettaglio e layout su desktop e smartphone; 24 prove «al contrario» (16 backend, 5 funzioni, 3 nel browser), tutte individuate. *Consegna 1:* backend 1269 test (nuovi: 22 sull'anagrafica e sulle regole di practice e utenti, 4 sul ruolo, 2 sulla migrazione; la matrice dei permessi copre le rotte nuove e il nuovo ruolo); frontend 235 test unitari (8 nuovi), tipi e compilazione; nel browser amministrazione (desktop e smartphone), accessibilità, editor, elenco, accesso, dashboard, dettaglio e layout; 12 prove «al contrario» sul backend, 5 sulle funzioni del frontend e 4 nel browser, tutte individuate (la prova sul nome unico ha richiesto di verificare anche il messaggio dell'applicazione, perché il vincolo del database risponde ugualmente 409).
- **Stato**: Consegnata
- **Commit**: questo commit

### CL-038 · 2026-10-20 · Accesso da programma a programma (account di servizio Google)
- **Richiesta**: far creare, modificare ed esportare CE a un portale esterno tramite connessione server-to-server con un account di servizio autorizzato; poi, in fase di piano, **assegnare da parte di un amministratore** un CE creato dall'account di servizio a un utente presale.
- **Tipo**: Funzione
- **Cosa è cambiato**: *consegne A (backend) e B (interfaccia) completate; manca la guida con lo script di collaudo (consegna C).* **Interfaccia (B):** scheda «Integrazioni» in Amministrazione (elenco, registrazione, modifica, disattivazione, indirizzo da usare come audience); pulsante «Assegna a un presale» nel dettaglio del CE (solo admin, solo per i CE creati da un'integrazione); autore «Nome (servizio)» e riga «Richiesto da»; etichette e dettagli in cronologia. **Backend (A):** Nuova tabella `integrations` e utente di servizio (migrazione `0005`); verifica del token Google dell'account di servizio; contratto dedicato `/api/v1/integrazioni/…` (elenchi di supporto, elenco e riepilogo dei CE, creazione tutto-o-niente e ripetibile con `external_ref`, rilettura e sostituzione del contenuto delle proprie bozze con controllo di versione, PDF di riepilogo); gestione `/integrations` e assegnazione `POST /ce/{id}/assign` riservate agli amministratori; limite di una richiesta al secondo; impostazione `S2S_AUDIENCES` (Terraform e strumento di verifica dell'ambiente). Corretto in corsa un difetto: un token con issuer sbagliato avrebbe dato un errore 500 invece di 401. **Corretto dopo il rilascio della parte A:** la rilettura del contenuto riusava il tipo `ContentIn` in una risposta, e FastAPI lo divideva in `ContentIn-Input` e `ContentIn-Output`: il frontend non trovava più `ContentIn` e il lint falliva in CI. Ora quel campo è un oggetto generico, dello stesso formato del corpo del PUT; un test fa fallire il backend se un tipo si divide ancora, e il confronto con lo schema precedente alla funzione mostra solo aggiunte (tre campi nuovi).
- **Decisioni**: il portale esterno gira su Google Cloud, con account separati per test e produzione; crea CE con tutto il contenuto, modifica solo le **proprie bozze** (o rifiutate), legge elenchi e riepiloghi di **tutti** i CE, esporta **solo il PDF di riepilogo** (giornate e ricavi, di tutti i CE, anche non approvati con l'avviso «Versione non approvata»); non invia in approvazione né approva; non vede costi né margini. Autore: un **utente di servizio** collegato all'integrazione, con il campo informativo «richiesto da» (email della persona). Percorso dedicato `/api/v1/integrazioni/…`, al massimo **una chiamata al secondo** per integrazione. Il token è un ID token Google dell'account di servizio, verificato dal portale (firma, scadenza, audience, email) e confrontato con l'elenco gestito dall'amministratore. Un amministratore può **assegnare a un presale** un CE creato da un'integrazione; da quel momento l'integrazione non può più modificarlo.
- **Verifica**: *parti A e B.* **B:** 227 test unitari (nuovi: funzioni pure delle integrazioni e dettagli della cronologia), test nel browser su desktop e smartphone per la scheda, il flusso di assegnazione (stato di partenza simulato: il server vero non crea CE «da integrazione» senza un token Google) e i permessi, accessibilità della pagina e del modulo; 10 prove «al contrario» sul frontend, tutte individuate. Il passo `browser` della skill avviava Chromium con `--single-process`, che lo faceva chiudere a metà: corretto. **A:** Test nuovi per gestione, accesso, firma reale del token (chiave generata in locale: token scaduti, alterati, per un altro indirizzo), contratto, assegnazione, matrice dei permessi del contratto e migrazione; circa 25 prove «al contrario», tutte individuate dopo aver aggiunto i test che mancavano. Terraform controllato solo nella sintassi (`tofu fmt`): piano e `terraform test` li esegue la CI. Mai provato con un token Google vero: serve il collaudo nell'ambiente di test.
- **Stato**: In corso
- **Commit**: questo commit

### CL-037 · 2026-10-19 · Documentazione Swagger delle API in un solo file
- **Richiesta**: «posso avere lo swagger di FastAPI» (dopo aver chiesto come richiamare le API dall'esterno).
- **Tipo**: Strumenti
- **Cosa è cambiato**: nuovo comando `make api-docs` (script `backend/scripts/build_swagger_html.py`) che scrive `api-swagger.html`: la documentazione Swagger di tutte le API in **un solo file** (circa 2 MB, 68 operazioni), che si apre con un doppio clic, anche offline, senza server. Il file generato non è nel repository (`.gitignore`) e va rigenerato quando le API cambiano. Nota in `docs/api.md`.
- **Decisioni**: `/docs` e lo schema restano **spenti in produzione** (la documentazione non si espone); il file è di **sola lettura**: «Try it out» è spento perché dal file il browser bloccherebbe le chiamate (il portale accetta solo la propria origine), e per provarle si usa `/docs` in locale. Le istruzioni di accesso (token Google, token di sessione di 8 ore, ruoli) sono nella descrizione della pagina. Lo schema viene da `frontend/openapi.json`, già tenuto allineato al codice dalla CI.
- **Verifica**: 3 test nuovi (lo schema resta JSON valido e nessun testo chiude in anticipo i tag, nessuna risorsa esterna, «Try it out» spento, lo schema in ingresso non cambia); 5 prove «al contrario» individuate; il file generato aperto in un browser: 68 operazioni visibili in 13 gruppi, nessun errore e nessuna richiesta di rete. L'ambiente di test del portale non è stato provato: la sua pagina `/docs` standard probabilmente non si vede per la politica di sicurezza sugli script (da verificare se servisse).
- **Stato**: Consegnata
- **Commit**: 8727d2b

### CL-036 · 2026-10-15 · PDF dei CE più curati: stile moderno del marchio
- **Richiesta**: rendere i PDF dei report «un po' più gradevoli esteticamente», con colori ed effetti grafici moderni ma chiari, puliti e professionali; poi, scelto lo stile B del mockup, **ciambella al posto della barra costi/margine** (come nello stile C) e il simbolo € nei riquadri «come ora».
- **Tipo**: Funzione
- **Cosa è cambiato**: i due PDF dei CE (completo e riepilogo) hanno la fascia nera con il logo bianco e un filo sfumato ciano-turchese, i riquadri per gli indicatori (prezzo in ciano), la **ciambella** del margine e le barre per profilo o per fase (grafica vettoriale), le tabelle con intestazioni turchesi, una fascia sottile nelle pagine successive e il piè di pagina su fondo chiaro. Font **DM Sans** incorporato (con la licenza OFL) al posto di Helvetica, colori del marchio al posto del blu generico. Corretto il difetto per cui nel riepilogo il titolo si sovrapponeva al logo. Nuovo `logo-white.png` per la fascia.
- **Decisioni**: stile B scelto dopo un mockup con i dati dell'utente (tre stili e quattro modi di mostrare l'€); simbolo € nei riquadri invariato (`34.750,00 €`); il riepilogo del viewer mostra solo giornate e ricavi per fase, senza ciambella. Se i font mancano si ripiega su Helvetica; un logo personalizzato senza versione bianca va su una piastra chiara.
- **Verifica**: 19 test dei PDF verdi (10 nuovi: font incorporato e ripiego, licenza, riquadri, ciambella e barre, fascia sottile, logo, casi limite della ciambella, testi lunghi e importi grandi, riepilogo senza parole riservate); 10 prove «al contrario» individuate; pagine generate dai dati demo e guardate a occhio (completo di una e di quattro pagine, riepilogo, titolo lunghissimo, CE vuoto). La stampa in bianco e nero è stata simulata solo nel mockup, non sul file vero.
- **Stato**: Consegnata
- **Commit**: 24ef67f

### CL-035 · 2026-10-15 · Chatbot conversazionale e server MCP (valutati e scartati)
- **Richiesta**: «aggiungere un MCP Server e un chatbot conversazionale: è possibile?»
- **Tipo**: Funzione
- **Cosa è cambiato**: nulla nel portale. È stata valutata la fattibilità (server MCP con trasporto HTTP e autorizzazione OAuth, chatbot nel portale, un livello comune di strumenti in sola lettura che riusa le funzioni esistenti) ed è stato proposto un elenco di domande per il brainstorming.
- **Decisioni**: l'utente ha deciso di **non sviluppare** la funzione: valore percepito basso rispetto ai rischi di sicurezza e privacy. I punti critici emersi: i dati (clienti, costi, margini, tariffe) verrebbero inviati a un fornitore di modelli; i permessi per ruolo andrebbero replicati (il viewer non deve mai vedere costi e margini); il testo libero dei CE può contenere istruzioni travestite da dati; i costi per messaggio vanno limitati. Non si riapre senza una nuova richiesta dell'utente.
- **Verifica**: nessuna, non è stato scritto codice. Le informazioni sul protocollo e sulle API di Claude vengono dalla documentazione consultata il 2026-10-15.
- **Stato**: Annullata
- **Commit**: e0eebaf

### CL-034 · 2026-10-14 · Consegna copiata solo in parte: controllo nelle prove e verifica della copia
- **Richiesta**: errore della pipeline del backend su GitHub dopo la consegna delle practice: `relation "practices" does not exist` in molte prove (screenshot e log completo).
- **Tipo**: Correzione
- **Cosa è cambiato**: **nessuna modifica al portale**. Causa: la consegna di CL-033 è arrivata nel repository solo in parte. I numeri di riga del log lo mostrano: `app/models/accounts.py` era la versione nuova, `tests/dash_helpers.py` quella vecchia, e la migrazione `0004` non c'era, quindi il database di test non aveva la tabella. Aggiunto un controllo all'avvio delle prove (`backend/tests/conftest.py`): se modelli e migrazioni non coincidono le prove **si fermano subito con un messaggio chiaro** invece di fallire una per una. In `CONTRIBUTING.md` la procedura per copiare una consegna e verificarla file per file. La consegna è ora **cumulativa**.
- **Decisioni**: il controllo ferma la sessione di prove (`pytest.exit`) e non si limita a segnalare; la verifica della copia si fa con un confronto file per file, senza aggiungere file al repository.
- **Verifica**: simulato il caso (migrazione `0004` tolta, modelli nuovi): le prove si fermano con il messaggio che nomina la tabella `practices`; con la migrazione presente partono; suite completa verde (996, 0 saltati). Non ho potuto vedere il repository dell'utente: la diagnosi viene dai numeri di riga del log.
- **Stato**: Consegnata
- **Commit**: 5936a3d

### CL-033 · 2026-10-14 · Practice dei collaboratori e carico risorse per practice
- **Richiesta**: «aggiungere una tabella "Practice" e fare in modo che a ogni collaboratore sia associata una practice» (non serve vederla sulle righe del CE, basta che sia associata al collaboratore) e fare in modo che, dopo l'inserimento, anche i report del carico, oltre che per persona, siano fatti anche per practice.
- **Tipo**: Funzione
- **Cosa è cambiato**: nuova anagrafica **Practice** (nome unico senza distinzione di maiuscole, si disattiva, non si elimina) con scheda in *Amministrazione*; ogni collaboratore ha **una practice obbligatoria** (campo nella scheda, colonna e filtro nell'elenco, colonna `Practice` facoltativa nell'importazione CSV). **Carico risorse**: nuova sezione «Impegno per practice» sopra la tabella delle persone (stesso selettore Percentuale/Giorni/Ore/Entrambi e stessa mappa di calore), filtro «Practice» anche per l'esportazione; l'Excel ha un foglio «Practice» e il CSV le colonne «Practice» e «Persone» **in coda**. Migrazione `0004`, API (`/practices`, `practice_id` nei collaboratori e nel carico), dati demo con tre practice di esempio.
- **Decisioni**: practice obbligatoria; i collaboratori già presenti partono con la practice di sistema **«Da assegnare»** (che non si rinomina né si disattiva); **percentuale di una practice = giorni ÷ (persone che hanno impegno nel periodo × giorni lavorativi del mese)**; practice **attuale per tutto il periodo** (nessuno storico); vista A (sezione separata sopra le persone), scelta dopo un mockup con i dati dell'utente. Fuori dalle righe del CE e dal Portfolio. Un file di importazione senza la colonna, o con la cella vuota, assegna «Da assegnare» ai nuovi e non cambia gli esistenti. Esiste già un **profilo** di listino chiamato «Practice»: concetto diverso, lasciato com'è (annotato in `manutenzione.md`).
- **Verifica**: backend 996 test verdi, 0 saltati (74 nuovi, 15 prove «al contrario» individuate); migrazione provata su un database con 47 collaboratori, reversibile, `alembic check` pulito; schema API committato uguale a quello generato. Frontend: 214 test unitari; browser: amministrazione verde su desktop (25, 2 saltati) e smartphone (26, 1 saltato), dashboard e accessibilità 26 + 26; 2 prove «al contrario» nel browser. Non rieseguiti: l'editor e le altre suite del browser. Mai provato su Google Cloud né in CI.
- **Stato**: Consegnata
- **Commit**: b835333

### CL-032 · 2026-10-13 · Test del listino: indipendenti dai dati lasciati da altri test
- **Richiesta**: errore della CI, test «le tariffe 2026 coincidono con il listino» (giro smartphone): la riga «Senior» mostrava «nessuna tariffa» e il pulsante si chiamava «Tariffa 2027».
- **Tipo**: Correzione
- **Cosa è cambiato**: solo test. I test del listino aprono la pagina con l'anno esplicito (`/admin/listino?anno=2026`). Il test dell'editor su «profilo di default senza tariffa» (CL-031) usa una tariffa di un anno passato e a fine test la elimina: prima lasciava una tariffa 2027 nel database.
- **Decisioni**: la pagina del listino **non cambia**: si apre sull'ultimo anno con tariffe, ed è voluto (quando si carica il listino del nuovo anno, l'amministratore lo trova subito). La causa era mia: il database della CI è condiviso tra il giro desktop e quello smartphone, quindi il dato lasciato dal primo faceva fallire tre test del secondo.
- **Verifica**: riprodotto nel sandbox lasciando una tariffa 2027 (3 test del listino fallivano, stesso testo della CI); con la correzione passano anche con la tariffa presente; il test dell'editor lascia gli anni con tariffe a `[2026]` dopo desktop e smartphone; amministrazione completa verde su desktop (21, 2 saltati) e smartphone (22, 1 saltato). Il resto della suite non rieseguito.
- **Stato**: Consegnata
- **Commit**: 8a55de0

### CL-031 · 2026-10-13 · Editor: prima il collaboratore, poi il profilo (che lo segue)
- **Richiesta**: «per velocizzare l'inserimento dei dati nell'inserimento delle attività sul conto economico vorrei che venisse richiesto prima il collaboratore e che poi venisse caricato il profilo di default come indicato in anagrafica collaboratore (avendo sempre la possibilità di modificarlo)».
- **Tipo**: Funzione
- **Cosa è cambiato**: nella griglia delle righe le colonne sono ora Attività, **Collaboratore**, **Profilo**, PM (anche l'ordine con il tasto Tab). Scegliendo il collaboratore il profilo si carica con il suo profilo di default e resta modificabile. Se quel profilo non ha la tariffa dell'anno del CE (o è disattivato) la riga conserva il suo profilo e mostra una nota, collegata al campo per i lettori di schermo.
- **Decisioni**: scelta dell'utente: il profilo **segue sempre** il collaboratore, anche se era stato cambiato a mano (alternative scartate: seguirlo solo se non modificato a mano; solo alla prima scelta). Togliendo il collaboratore il profilo non cambia; una riga nuova continua a ereditare il profilo dell'ultima. Nessuna modifica ai dati salvati né all'API: il profilo resta obbligatorio, controllato anche dal server.
- **Verifica**: 206 test unitari (10 nuovi sulla regola); 7 prove «al contrario» sulla regola individuate; browser: editor completo verde su desktop (31, 2 saltati perché solo smartphone) e smartphone (33), accessibilità 12 verdi; i test nuovi falliscono con la regola e l'ordine vecchi per il motivo giusto. Osservazione (non modificata): durante il ricalcolo dei totali la barra è attenuata e le etichette piccole scendono sotto il contrasto AA (annotato in `manutenzione.md`). Backend non toccato e non rieseguito. Nota: il test sul profilo senza tariffa lasciava una tariffa 2027 nel database e ha fatto fallire tre test del listino nella CI: corretto in CL-032.
- **Stato**: Consegnata
- **Commit**: 27978f2

### CL-030 · 2026-10-13 · Registro delle modifiche
- **Richiesta**: tenere traccia di tutte le richieste di modifica in un file `changelog.md` nella cartella della documentazione, aggiornarlo a ogni richiesta di funzionalità aggiuntiva e, se serve, aggiornare anche la skill.
- **Tipo**: Documentazione
- **Cosa è cambiato**: nuovo `docs/changelog.md` con la storia ricostruita dai commit (CL-001 - CL-030); regola in `CONTRIBUTING.md`; test `test_changelog.py` che ne controlla il formato; la skill `portale-ce-sviluppo` ha ora la regola e un modello di voce (`references/registro-modifiche.md`).
- **Verifica**: test del formato del registro e di coerenza della documentazione verdi; prove «al contrario» sul test. Le voci precedenti sono ricostruite dai commit e dalla conversazione: le date sono quelle dei commit.
- **Stato**: Consegnata
- **Commit**: fae9728

### CL-029 · 2026-10-13 · Carico risorse: modalità «Ore»
- **Richiesta**: «aggiungere un tasto Ore per visualizzare l'impegno sul singolo mese in ore» nella dashboard dell'impegno collaboratori.
- **Tipo**: Funzione
- **Cosa è cambiato**: quarto pulsante «Ore» nel selettore «Mostra nelle celle»; le celle mostrano le ore con un decimale (arrotondamento da 5 in su). `?celle=ore` nell'indirizzo.
- **Decisioni**: totale a destra e riga della capacità del mese **restano in giorni** (scelta dell'utente); «Entrambi» resta percentuale e giorni; le ore sono quelle del server (giorni × 8), nessun ricalcolo nel browser, nessuna modifica all'API.
- **Verifica**: 196 test unitari; 8 prove «al contrario» individuate; browser (dashboard e accessibilità) 25 verdi su desktop e 25 su smartphone. Backend e resto della suite non rieseguiti (non toccati).
- **Stato**: Consegnata
- **Commit**: 65a293e

### CL-028 · 2026-10-13 · Skill di contesto del progetto
- **Richiesta**: creare una skill con il metodo di lavoro della richiesta iniziale, gli strumenti (Python, FastAPI, React, GitHub…), le preferenze grafiche (loghi, colori, font) e che si usi anche per le modifiche al codice esistente.
- **Tipo**: Strumenti
- **Cosa è cambiato**: skill `portale-ce-sviluppo` (fuori dal repository) con metodo, stack, grafica, regole di dominio, checklist per tipo di modifica, verifica e consegna, script di preparazione del sandbox; poi preferenze confermate dall'utente (piano breve con ok per le funzioni medie, zip dei soli file modificati, verifica completa per le funzioni e leggera per i ritocchi) e documento unico `.md`.
- **Verifica**: validazione ufficiale della skill, 52 percorsi citati esistenti, script eseguito passo per passo. Non provata in una conversazione nuova.
- **Stato**: Consegnata

### CL-027 · 2026-10-12 · Scelta del cliente: niente clienti disattivati
- **Richiesta**: errore della CI nel test «crea, modifica e disattiva: un cliente disattivato esce dalle scelte» (solo su smartphone).
- **Tipo**: Correzione
- **Cosa è cambiato**: la scelta del cliente (nuovo CE, duplicazione, editor) offre solo i clienti attivi più quello già assegnato al CE, con «(disattivato)»; i filtri dell'elenco restano completi. Il test del browser aspetta ora che l'elenco sia caricato prima di dire che un'opzione manca.
- **Decisioni**: nessuna modifica al backend (il server già rifiutava un cliente disattivato nuovo). Limite noto: gli elenchi mostrano al massimo 200 clienti.
- **Verifica**: i due test falliscono sul comportamento vecchio con lo stesso sintomo della CI e passano con la correzione; 193 test unitari; amministrazione verde su desktop (21) e smartphone (22).
- **Stato**: Consegnata
- **Commit**: b059dde

### CL-026 · 2026-10-12 · Carico risorse: giorni oltre alla percentuale
- **Richiesta**: «oltre alla % di occupazione per singola persona puoi indicare anche i giorni?», con mockup prima.
- **Tipo**: Funzione
- **Cosa è cambiato**: selettore «Mostra nelle celle» (Percentuale, Giorni, **Entrambi** predefinito); in «Entrambi» percentuale e sotto i giorni (`10,8 gg`); la scelta sta nell'indirizzo (`?celle=`) e «Azzera filtri» non la toglie. Corretto un arrotondamento: 19,95 giorni appariva «19,9» (ora «20,0», da 5 in su sulle cifre scritte).
- **Decisioni**: variante «Entrambi» scelta dopo un mockup interattivo con i dati dell'utente.
- **Verifica**: 186 test unitari; 9 prove «al contrario» individuate; browser verde su desktop e smartphone.
- **Stato**: Consegnata (la funzione compare in uno screenshot inviato dall'utente il 13/10, senza indicare in quale ambiente)
- **Commit**: 38ef691

### CL-025 · 2026-10-12 · Documentazione finale (passo 11)
- **Richiesta**: proseguire col passo 11, la documentazione, dopo che l'utente ha riferito «al momento funziona tutto in ambiente di test».
- **Tipo**: Documentazione
- **Cosa è cambiato**: guida all'uso, architettura riscritta (un solo servizio), manutenzione ed emergenze, README e guida di pubblicazione aggiornati; test `test_docs.py` (collegamenti, ancore, comandi `make`, percorsi citati).
- **Verifica**: test di coerenza della documentazione verdi, con prove «al contrario».
- **Stato**: Consegnata
- **Commit**: 5e03368

### CL-024 · 2026-10-12 · Collaudo sull'ambiente reale (passo 10)
- **Richiesta**: «Ok procediamo col punto successivo» (dopo la guida di pubblicazione).
- **Tipo**: Strumenti
- **Cosa è cambiato**: `infra/scripts/check_env.py` (controllo in sola lettura dell'ambiente su Google Cloud) e guida `docs/collaudo.md` con le prove nel browser, di operatività e sicurezza e il passaggio in produzione.
- **Verifica**: 25 test con `gcloud` e `curl` simulati, 13 prove «al contrario» individuate. Mai eseguito su un progetto Google Cloud vero; il collaudo formale e la produzione restano da eseguire.
- **Stato**: Consegnata
- **Commit**: 04239da

### CL-023 · 2026-10-10 · CI: controllo di salute del database
- **Richiesta**: errore nei log della CI (`FATAL: database "ceportal" does not exist`).
- **Tipo**: Correzione
- **Cosa è cambiato**: il controllo di salute cerca il database giusto; sparisce il rumore nei log. Non era un errore dei test.
- **Verifica**: actionlint.
- **Stato**: Consegnata
- **Commit**: ef9ffc0

### CL-022 · 2026-10-10 · CI: script lanciati con `bash`
- **Richiesta**: errore «Permission denied» (codice 126) nel passo «Controllo delle variabili del repository».
- **Tipo**: Correzione
- **Cosa è cambiato**: i flussi lanciano gli script con `bash script.sh` (il permesso di esecuzione si perde passando da uno zip); test `test_workflows.py` che lo impone.
- **Verifica**: prova «al contrario» (test fallisce reintroducendo una invocazione diretta); actionlint e shellcheck.
- **Stato**: Consegnata
- **Commit**: 276bb3f

### CL-021 · 2026-10-10 · CI: versioni delle librerie fissate
- **Richiesta**: errore «frontend/openapi.json non è aggiornato» nella CI.
- **Tipo**: Correzione
- **Cosa è cambiato**: la CI installa le versioni esatte di `backend/requirements-dev.lock` (la CI usava le ultime, e una nuova `pydantic` cambiava lo schema dell'API); `make lock` produce entrambi i file; test di coerenza.
- **Decisioni**: dopo ogni aggiornamento delle librerie: `make lock` e `make api-types`.
- **Verifica**: schema generato con le versioni fissate identico a quello versionato; 893 test del backend verdi.
- **Stato**: Consegnata
- **Commit**: 8cc74f3

### CL-020 · 2026-10-10 · Avvio manuale di CI e Infrastruttura
- **Richiesta**: «non partono le github actions c'è un modo per forzare push».
- **Tipo**: Ritocco
- **Cosa è cambiato**: `workflow_dispatch` in `ci.yml` e `infra.yml` («Run workflow»); riga di troubleshooting nella guida.
- **Verifica**: actionlint.
- **Stato**: Consegnata
- **Commit**: 1ba9868

### CL-019 · 2026-10-10 · CI Infrastruttura: test di Terraform indipendenti dai valori calcolati
- **Richiesta**: errore del passo «Test del modulo (provider simulati)» nella CI.
- **Tipo**: Correzione
- **Cosa è cambiato**: il test non confronta più attributi «calcolati» (che Terraform e OpenTofu simulano in modo diverso): controlla i nomi delle variabili per GitHub e i valori in ingresso.
- **Verifica**: con OpenTofu 21 test verdi e prova «al contrario»; **non** provato con Terraform vero (non disponibile nel sandbox).
- **Stato**: Consegnata
- **Commit**: dc82caa

### CL-018 · 2026-10-10 · Email nel test: modalità `console`
- **Richiesta**: «le mail sembrano non funzionare sull'ambiente di test».
- **Tipo**: Documentazione
- **Cosa è cambiato**: spiegato che nel test `mail_backend` vale `console` (nessuna email vera) per impostazione predefinita; esempi `terraform.tfvars` e riga di troubleshooting.
- **Verifica**: solo documentazione (descrive un'impostazione dell'ambiente reale: nessuna prova eseguibile dal sandbox).
- **Stato**: Consegnata
- **Commit**: 5c8fa40

### CL-017 · 2026-10-09 · Accesso Google: «no registered origin»
- **Richiesta**: errore «Access blocked: Authorization Error / invalid_client» al login.
- **Tipo**: Documentazione
- **Cosa è cambiato**: causa (indirizzo non tra le origini JavaScript autorizzate del Client ID) e rimedio nella guida di pubblicazione.
- **Verifica**: solo documentazione (la causa viene dall'errore mostrato dall'utente; l'accesso con Google vero non è raggiungibile dal sandbox).
- **Stato**: Consegnata
- **Commit**: 655b97f

### CL-016 · 2026-10-09 · Flussi GitHub: accesso a Google Cloud
- **Richiesta**: errori dell'azione di accesso («exactly one of workload_identity_provider…», «Invalid value for audience»).
- **Tipo**: Correzione
- **Cosa è cambiato**: passi con nomi chiari; controllo dei parametri nel flusso riusabile; controllo del formato del fornitore di identità (mostra il valore ricevuto); le pubblicazioni leggono le variabili dentro il proprio Environment; un valore segnaposto «-» conta come non impostato.
- **Decisioni**: GitHub non accetta variabili vuote: le `PROD_…` non vanno create finché non esiste la produzione.
- **Verifica**: 7 scenari dello script di controllo, actionlint e shellcheck; non eseguito su GitHub Actions vero.
- **Stato**: Pubblicata sul test
- **Commit**: eaeb30e, b1b85c4, dfb6f38

### CL-015 · 2026-10-09 · Flussi GitHub: variabili del repository
- **Richiesta**: errore di pubblicazione nel registro del progetto sbagliato (`…/hw-ce-portal-test/…`).
- **Tipo**: Correzione
- **Cosa è cambiato**: `check-deploy-vars.sh` controlla le variabili prima di pubblicare e mostra progetto e registro; la produzione è facoltativa; Terraform stampa nomi e valori esatti delle variabili (`github_variables`) e i comandi `gh`.
- **Verifica**: scenari dello script, actionlint, shellcheck, test Terraform con provider simulati (21).
- **Stato**: Pubblicata sul test
- **Commit**: 0787855, 201c79f

### CL-014 · 2026-10-09 · Servizio pubblico con policy che vieta `allUsers`
- **Richiesta**: errore di `terraform apply` («users … do not belong to a permitted customer»).
- **Tipo**: Infrastruttura
- **Cosa è cambiato**: variabile `public_access_method = "disable_iam_check"` (servizio pubblico senza assegnare `allUsers`).
- **Decisioni**: in alternativa, eccezione alla policy dell'organizzazione per il solo progetto.
- **Verifica**: formato, validità e test del modulo (19 con provider simulati) con OpenTofu; **non** provato su Google Cloud.
- **Stato**: Pubblicata sul test
- **Commit**: c059042

### CL-013 · 2026-10-07 · Infrastruttura e pubblicazione (passo 9)
- **Richiesta**: «vai col passo 9».
- **Tipo**: Infrastruttura
- **Cosa è cambiato**: immagine unica (backend + frontend), Terraform (Cloud Run, Cloud SQL, segreti, lavori, Scheduler, avvisi, accesso GitHub senza chiavi), flussi di pubblicazione con approvazione per la produzione, `/api/v1/config`, intestazioni di sicurezza, log JSON, versioni fisse delle dipendenze, guida `deploy.md`.
- **Decisioni**: un solo servizio per ambiente; una sola immagine per test e produzione; ambienti in progetti separati.
- **Verifica**: backend 889 verdi; contenitore simulato passo per passo; hadolint, actionlint, shellcheck; OpenTofu. Mai eseguito su Google Cloud dal sandbox.
- **Stato**: Pubblicata sul test (riferito dall'utente: «funziona tutto in ambiente di test»)
- **Commit**: 8518118

### CL-012 · 2026-10-07 · Amministrazione nel frontend (passo 8d)
- **Richiesta**: «si procedi» (amministrazione dopo dashboard).
- **Tipo**: Funzione
- **Cosa è cambiato**: schede per utenti, clienti, collaboratori, listino con tariffe per anno, calendario, email, CE eliminati (con ripristino); importazione CSV con controllo prima della scrittura.
- **Verifica**: 148 test unitari; browser desktop 102 e smartphone 110; accessibilità; prove «al contrario».
- **Stato**: Pubblicata sul test
- **Commit**: 892f43a

### CL-011 · 2026-10-07 · Dashboard nel frontend (passo 8c)
- **Richiesta**: scelta dei grafici: «vanno bene anche grafici semplici».
- **Tipo**: Funzione
- **Cosa è cambiato**: dashboard *Portfolio* e *Carico risorse*, grafici SVG semplici con tabelle equivalenti per i lettori di schermo, esportazione Excel e CSV.
- **Verifica**: 131 test unitari; browser desktop 81 e smartphone 88; accessibilità.
- **Stato**: Pubblicata sul test
- **Commit**: 05cf69d

### CL-010 · 2026-10-07 · Creazione e modifica del CE (passo 8b)
- **Richiesta**: proseguire con la modifica del CE nel frontend.
- **Tipo**: Funzione
- **Cosa è cambiato**: nuovo CE, editor a ore o a percentuali con totali calcolati dal server, incolla da Excel, avviso di modifiche non salvate e di conflitto, azioni del workflow (invia, ritira, approva, rifiuta, nuova versione, scarta, riallinea, duplica, elimina).
- **Verifica**: browser desktop 65 e smartphone 72; corretti difetti trovati dai test (finestre annidate, scorrimento orizzontale su smartphone).
- **Stato**: Pubblicata sul test
- **Commit**: 51fec1b

### CL-009 · 2026-10-07 · `make demo` con l'amministratore del proprio database
- **Richiesta**: errore «Login simulato non riuscito per admin@huware.com: 403 Utente non abilitato».
- **Tipo**: Correzione
- **Cosa è cambiato**: `make demo` legge `BOOTSTRAP_ADMIN_EMAIL` da `backend/.env` (o `DEMO_ADMIN_EMAIL`) e spiega le cause se non riesce.
- **Verifica**: 5 scenari provati contro un database nuovo.
- **Stato**: Consegnata
- **Commit**: 26a08bd

### CL-008 · 2026-10-07 · Frontend: accesso, elenco, dettaglio, vista viewer (passo 8a)
- **Richiesta**: interfaccia moderna e responsive, ispirata a www.huware.com (colori, loghi, font).
- **Tipo**: Funzione
- **Cosa è cambiato**: accesso (Google e, in locale, simulato), elenco con filtri, dettaglio con indicatori e schede, vista riassuntiva del viewer; grafica Huware (DM Sans, ciano `#00f5fe`, turchese `#00acc7`).
- **Decisioni**: font DM Sans identificato a vista (da confermare); logo PNG a 410 px (SVG da richiedere).
- **Verifica**: 38 test unitari; 77 test nel browser su desktop e smartphone; accessibilità senza violazioni.
- **Stato**: Pubblicata sul test
- **Commit**: 1e8bb9e

### CL-007 · 2026-10-06 · Export e API delle dashboard (passo 7)
- **Richiesta**: Excel con formule vive, CSV e PDF; dashboard di portfolio e carico risorse.
- **Tipo**: Funzione
- **Cosa è cambiato**: export Excel (formule vive), CSV per Excel italiano, PDF completo e di riepilogo; API del portfolio (con pipeline separata) e del carico risorse (avviso oltre il 100%); riservatezza del viewer verificata sui file.
- **Verifica**: Excel validato con LibreOffice sul CE reale; test di riservatezza con prova di sensibilità; test isolati dalla rete e dall'ambiente.
- **Stato**: Pubblicata sul test
- **Commit**: 7d9dcaf, a3553bc

### CL-006 · 2026-10-06 · Notifiche email (passo 6)
- **Richiesta**: email per i passaggi di approvazione, con Mailjet.
- **Tipo**: Funzione
- **Cosa è cambiato**: 5 eventi (inviato in approvazione, approvato, rifiutato, nuova versione, nuovo utente); solo il prezzo, mai costi o margini; coda affidabile con ritentativi.
- **Verifica**: test con le variabili d'ambiente ignorate e le chiamate di rete esterne bloccate (rete di sicurezza introdotta in a3553bc); l'invio con Mailjet vero non è provabile dal sandbox. Conteggio dei test di quel passo non registrato.
- **Stato**: Pubblicata sul test
- **Commit**: c9f54d7

### CL-005 · 2026-10-05 · API dei CE (passo 5)
- **Richiesta**: gestione dei CE con approvazione, versioni e ricerca; vista ridotta per i viewer.
- **Tipo**: Funzione
- **Cosa è cambiato**: creazione, versioni, workflow (invia, ritira, approva, rifiuta), ricerca, duplicazione, storico, vista del viewer con schemi dedicati.
- **Verifica**: test delle API dei CE (workflow, versioni, ricerca, vista del viewer); conteggio dei test di quel passo non registrato.
- **Stato**: Pubblicata sul test
- **Commit**: 438b556

### CL-004 · 2026-10-05 · Motore di calcolo validato sul foglio reale (passo 4)
- **Richiesta**: calcoli identici al foglio di riferimento `PS-BONGA-AI-PJT`; regola dei giorni non lavorativi per ogni CE.
- **Tipo**: Funzione
- **Cosa è cambiato**: motore isolato in `Decimal` con modalità a ore e a percentuali, contingency per fase, prezzo minimo, fee media, prezzo firmato; regola dei giorni non lavorativi per mese nell'analisi funzionale.
- **Verifica**: risultati identici al foglio: 468 ore, 47.162,50 € di ricavi, 20.200,00 € di costi, 26.962,50 € di margine (57,17%), 58,5 giornate (anche con LibreOffice).
- **Stato**: Pubblicata sul test
- **Commit**: 3bd7146, dc55fcf

### CL-003 · 2026-10-05 · Accesso, utenti e anagrafiche (passo 3)
- **Richiesta**: login Google limitato al dominio, utenti registrati dall'amministratore, anagrafiche e importazioni.
- **Tipo**: Funzione
- **Cosa è cambiato**: accesso Google (e simulato in locale), ruoli admin/presale/viewer, clienti, collaboratori, profili e tariffe, calendario, importazioni CSV.
- **Verifica**: test delle API (accesso, ruoli, anagrafiche, importazioni); conteggio dei test di quel passo non registrato.
- **Stato**: Pubblicata sul test
- **Commit**: 53f9557

### CL-002 · 2026-10-05 · Modello dati (passo 2)
- **Richiesta**: PostgreSQL su Cloud SQL, versioni dei CE e storico.
- **Tipo**: Funzione
- **Cosa è cambiato**: schema con 16 tabelle e migrazione Alembic iniziale, dati iniziali (listino, festività), test del database.
- **Verifica**: test del database (vincoli, migrazione, dati iniziali); conteggio dei test di quel passo non registrato.
- **Stato**: Pubblicata sul test
- **Commit**: 190bf26

### CL-001 · 2026-10-03 · Avvio del progetto (passo 1)
- **Richiesta**: realizzare il portale per fasi (brainstorming, planning con conferme, sviluppo, test reale, documentazione) e ripetere lo schema per ogni funzionalità aggiuntiva; backend Python con OpenAPI, frontend React, PostgreSQL su Cloud SQL, Cloud Run con ambienti test e produzione, GitHub, accesso Google, email, interfaccia responsive.
- **Tipo**: Infrastruttura
- **Cosa è cambiato**: repository, struttura del monorepo, CI di base; analisi funzionale approvata dall'utente dopo il brainstorming.
- **Verifica**: struttura e CI di base; l'analisi funzionale è stata approvata dall'utente prima dello sviluppo.
- **Stato**: Pubblicata sul test
- **Commit**: 86f32fb
