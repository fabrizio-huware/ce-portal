# Analisi funzionale (v1.0 – approvata)

## 1. Obiettivo
Portale interno per creare, memorizzare, modificare e ricercare i Conti Economici (CE) di progetto, con calcolo di costi, ricavi, margini e impegno delle risorse. L'approvazione dei CE è riservata all'admin e, per un CE in approvazione che coinvolge la sua business unit, al responsabile di business unit (modifica CL-039).

## 2. Ruoli e permessi

| Funzione | Admin | Presale | Responsabile di business unit | Viewer |
|---|---|---|---|---|
| Gestione utenti, listini, calendario, anagrafiche, business unit | sì | no | no | no |
| Creare / duplicare CE | sì | sì | sì | no |
| Modificare CE | tutti | solo i propri | solo i propri | no |
| Inviare in approvazione | sì | sì | sì | no |
| Approvare e rifiutare | sì (approva sempre, anche da Bozza) | no | solo un CE in approvazione che coinvolge la sua business unit | no |
| Eliminare CE (cancellazione logica) | sì | no | no | no |
| Cercare e visualizzare CE | tutti, vista completa | vista completa: tutti, oppure — con la visibilità per business unit accesa — quelli che coinvolgono la sua business unit e i propri | come il presale | solo CE approvati, vista riassuntiva |

**Vista riassuntiva del viewer**: giornate di Management, giornate di Delivery, ricavi per fase, totale generale. Nessun costo, margine, staffing o dettaglio righe. Gli export rispettano la stessa visibilità. Il viewer non accede alle dashboard portfolio e carico risorse.

## 2 bis. Business unit e visibilità (modifica CL-039)

- **Gerarchia**: business unit → practice → collaboratori. Una practice sta in **una** business unit; «Da assegnare» è la business unit di sistema delle practice non ancora assegnate. Ogni presale può avere una business unit; il responsabile di business unit ne ha una obbligatoriamente.
- **Business unit coinvolte in un CE**: si dichiarano alla creazione (almeno una, vere e attive) e valgono per **tutto il CE**; le cambiano l'autore e l'admin finché è bozza o rifiutato (l'admin, in qualunque stato, solo se il CE non ne ha nessuna), con registro. Le business unit dei collaboratori delle righe devono essere tra quelle coinvolte: altrimenti l'**invio in approvazione è bloccato**.
- **Visibilità per business unit**: un interruttore dell'amministrazione, **spento alla pubblicazione**. Acceso, un presale o un responsabile vede un CE se la sua business unit è coinvolta **oppure** se ne è l'autore, **per intero** (costi e margini compresi). Un CE che non vede risponde «non trovato». L'admin vede tutto; viewer e integrazioni non cambiano. Elenco, esportazioni, Portfolio e Carico risorse seguono la regola: nel Carico risorse un presale o un responsabile vede solo le persone della sua business unit, con il carico calcolato su tutti i CE.
- **Approvazione del responsabile**: un CE in approvazione che coinvolge la sua business unit (con più business unit ne basta una); l'admin approva sempre.
- **Fuori ambito**: ripartizione dei ricavi per business unit in base alle righe, notifiche per i responsabili, un responsabile che non può approvare i propri CE.

## 2 ter. Esito della trattativa (modifica CL-042)

- Su un CE con l'**ultima versione approvata** si può segnare **Close Won** o **Close Lost**, con una nota facoltativa. L'esito sta sul CE; non cambia gli stati né il flusso di approvazione.
- Lo impostano, cambiano e tolgono l'admin, il responsabile di una business unit coinvolta e l'autore, sempre registrato nello storico.
- Dopo **Close Lost** non si crea una nuova versione finché l'esito non viene tolto; un CE **con esito non si elimina**, e l'interfaccia lo segnala.
- Il viewer e le integrazioni vedono l'esito (in sola lettura), non la nota. Le integrazioni non lo impostano.

## 3. Entità
- **Utente**: email Google, ruolo (admin, presale, responsabile di business unit, viewer), business unit (presale e responsabili), attivo/non attivo. Registrato dall'admin; login Google limitato al dominio huware.com.
- **Cliente**: ragione sociale, indirizzo. Creabile da admin e presale.
- **Collaboratore**: nome, cognome, profilo di default, **practice** (obbligatoria), attivo/non attivo. Anagrafica separata dagli utenti; import CSV iniziale.
- **Business unit** (CL-039): sta sopra le practice; si crea, si rinomina e si disattiva, non si elimina; «Da assegnare» è di sistema.
- **Practice** (modifica del 13/10/2026, CL-033; business unit dal CL-039): area di competenza; un collaboratore ne ha **una**, obbligatoria (chi esisteva prima parte con «Da assegnare»). Non compare nelle righe del CE: serve ai report. Si gestisce da *Amministrazione*; non si elimina, si disattiva. Vedi [dashboard.md](dashboard.md).
- **Profilo (listino)**: nome, prezzo/giorno, costo/giorno, anno di validità, indicatore "esterno" (profilo **Esterni**, che confluisce in Servizi Esterni). Gestito dall'admin. Banda e billability target facoltativi, non usati nei calcoli.
- **CE Testata**: codice progetto (univoco, manuale), progetto, cliente, SF Opp, **business unit coinvolte** (elenco, dal CL-039: non più un testo libero), note, data inizio, data fine, stato, modalità di pianificazione, **max sconto %** (inserito da chi compila), prezzo firmato, versione, autore.
- **CE Fase**: nome, % di contingency.
- **CE Riga**: fase, attività, collaboratore (facoltativo), profilo (anche "Esterni"), flag "Project Management", ore oppure % mensili. Nell'inserimento si sceglie prima il collaboratore e il profilo si carica con quello di default dell'anagrafica (modifica del 13/10/2026, CL-031), sempre modificabile.
- **Di supporto**: calendario festività e chiusure aziendali (admin, usato come suggerimento), giorni non lavorativi per mese di ogni versione di CE, milestone, versioni CE, audit log.

## 4. Regole funzionali
- Modalità di pianificazione unica per CE: ore dirette oppure % mensile.
- Durata massima 12 mesi.
- 1 giorno = 8 ore. **Giorni lavorativi del mese** = giorni lun-ven del **mese intero** meno i "giorni non lavorativi" del mese inseriti sul CE (come nel foglio). Il mese di inizio e quello di fine contano per intero (nessun pro-rata): le date del progetto stabiliscono solo quali mesi compaiono.
- **Giorni non lavorativi sul singolo CE**: per ogni mese del progetto si inserisce a mano il **numero** di giorni non lavorativi feriali (festività, chiusure), come nella riga "NO-WORK DAYS" del foglio. Alla creazione il valore si precompila dal calendario generale dell'admin (festività e chiusure che cadono di lunedì-venerdì) ed è modificabile. È **congelato nella versione**, come le tariffe: le modifiche successive al calendario generale non alterano i CE esistenti e l'admin può riallineare un CE. Modificabile come il resto del CE (presale sui propri, admin su tutti; solo in bozza o rifiutato); una nuova versione eredita i valori della precedente; se il periodo si allunga, i mesi aggiunti si precompilano senza toccare quelli già modificati. Ogni modifica va nell'audit log.
- Modalità % mensile: % per riga e per mese, da 0 a 100%, applicata ai giorni lavorativi del mese intero. Giorni del mese = % × giorni lavorativi; FTE del mese = somma delle % (= giorni ÷ giorni lavorativi). Esplosione automatica in FTE, giorni, ore, ricavi e costi per mese (come "Staffing mensilizzato").
- Modalità ore dirette: matrice attività × profilo in **ore**. Le ore di ogni riga sono ripartite sui mesi in proporzione ai giorni lavorativi di ciascun mese (con somma esatta al centesimo di ora), per alimentare staffing e carico risorse.
- Prezzi e costi sempre dal profilo, congelati nel CE alla creazione; nessun override per riga; l'admin può riallineare al listino.
- **Servizi esterni**: si gestiscono come nel foglio, con il profilo **Esterni** (ore e tariffa/costo giornalieri del listino, es. 750 / 360). Le ore degli esterni contano nelle giornate totali. Costo e ricavo liberi non sono previsti. Fondi/PSF esclusi.
- Contingency per fase: % che aumenta i **ricavi** della fase (ricavo aggiuntivo = ricavi della fase × %, esterni inclusi) e le giornate "con contingency"; **non aggiunge costi**.
- Milestone opzionali, come etichette sui mesi.
- Workflow: Bozza → In approvazione → Approvato / Rifiutato. Una modifica a un CE approvato crea una nuova versione in Bozza, con storico consultabile e approvazione da rifare.
  - L'admin approva **sempre** (anche da bozza o da rifiutato). Il rifiuto richiede un motivo. Per inviare o approvare il CE deve contenere ore o percentuali.
  - **In approvazione** il CE è bloccato per il presale, che può solo ritirarlo; l'admin può comunque intervenire. Un CE rifiutato torna modificabile.
  - Una sola versione non approvata alla volta. Il viewer vede sempre l'ultima versione **approvata** finché la nuova non viene approvata. Si può scartare la versione in lavorazione (non la prima: per eliminare un CE serve l'admin).
  - Salvataggio con controllo di concorrenza: chi salva su dati nel frattempo modificati da altri riceve un avviso e non sovrascrive.
  - Alla creazione: tariffe dal listino dell'anno di inizio (errore se manca), giorni non lavorativi dal calendario generale, **fasi standard** del foglio (solo i nomi). Codice progetto in maiuscolo, univoco anche rispetto ai CE eliminati.
  - Il riallineamento (solo admin) aggiorna tariffe e/o calendario di una versione non approvata. La duplicazione crea un nuovo CE con tariffe e calendario correnti, senza copiare max sconto, prezzo firmato, opportunità Salesforce e note.
  - **Vista ridotta del viewer**: solo ultima versione approvata; codice, cliente, progetto, date, giornate di management e di delivery, ricavi per fase (contingency inclusa) e totale generale. Nessun costo, margine, ora, riga o tariffa, per costruzione.
- Duplicazione CE; cancellazione logica solo admin.
- Audit log delle modifiche; backup automatici.

## 5. Formule (validate sul foglio reale)
Le formule sono documentate in [formule.md](formule.md) con i riferimenti alle celle del foglio e i risultati del confronto. In sintesi:

- Costo riga = giorni × costo/giorno; Ricavo riga = giorni × prezzo/giorno; giorni = ore ÷ 8.
- Margine € = Ricavi − Costi; Margine % = Margine ÷ Ricavi; C/R = Costi ÷ Ricavi (nessuna divisione per zero: il valore è "n/d").
- Prezzo progetto = ricavi interni + ricavi esterni + ricavo da contingency.
- **Prezzo vendita min = Prezzo progetto × (1 − Max sconto)**, dove il max sconto è un valore inserito da chi compila.
- **Fee media min = Prezzo vendita min ÷ GG totali**; con prezzo firmato: Prezzo firmato ÷ GG totali.
- GG totali = giornate base (senza contingency, esterni inclusi); GG Project Management = giornate delle righe con il flag; GG tecniche = totale − PM; settimane = GG ÷ 5.
- Con prezzo firmato: Margine = Firmato − Costi; Margine % = Margine ÷ Firmato; C/R = Costi ÷ Firmato.
- Nessun arrotondamento nei passaggi intermedi: gli importi finali sono arrotondati al centesimo (mezzo centesimo per eccesso). La somma di voci arrotondate può quindi scostarsi di 1 centesimo dal totale, che è quello esatto.
- Differenza voluta rispetto al foglio: la contingency è calcolata **fase per fase**; il foglio applica al ricavo totale la media pesata sulle ore e sottostima quando le fasi hanno percentuali e mix di profili diversi.

## 6. Dashboard, ricerca, export, notifiche
- Dashboard: scheda KPI del CE; **portfolio** (approvati e, a parte, la pipeline: bozze e in approvazione di CE ancora senza versione approvata; per cliente, business unit, stato e mese); **carico risorse** per mese, collaboratore, **practice** e profilo (FTE sulla capacità del calendario generale, **avviso sopra il 100%**; per practice la percentuale è rispetto alle persone che hanno impegno nel periodo, con la practice attuale di ciascuno). Vedi [dashboard.md](dashboard.md).
- Ricerca: cliente, progetto, codice, date (da-a: progetti **attivi nel periodo**, cioè con periodo sovrapposto), stato, autore.
- Export: **Excel con formule vere** (modificabili per simulazioni), CSV per Excel italiano, PDF con logo; per ogni CE anche la variante **riepilogo** (senza costi). Il viewer ottiene solo la vista ridotta, in tutti i formati. Ogni esportazione è registrata e i file sono protetti dall'esecuzione di formule. Vedi [export.md](export.md).
- Email via Mailjet da teamdata@huware.com: CE inviato in approvazione → admin (escluso chi invia); CE approvato / rifiutato (con motivo) → autore; **nuova versione creata → admin**; nuovo utente abilitato → utente. Nelle email compare **solo il prezzo**, mai costi o margini; il viewer non riceve email sui CE. Invio affidabile con coda, ritentativi e gestione per l'admin: vedi [notifiche.md](notifiche.md).

## 7. Aspetti tecnici
Backend FastAPI (OpenAPI), frontend React + TypeScript responsive in italiano (EUR), PostgreSQL su Cloud SQL, Cloud Run con 2 ambienti (test, prod) in progetti separati, regione europe-west8, URL Cloud Run, monorepo GitHub con GitHub Actions. Design ispirato a huware.com (palette e font da validare nello Step 8). Campi per ID esterni predisposti per Jira e NetSuite.

## 8. Fuori ambito (per ora)
Override tariffe per riga, Fondi/PSF, campi Monday/Partners/EST, integrazioni Jira e NetSuite.
- **Chatbot conversazionale e server MCP** (valutati e scartati il 2026-10-15, CL-035): per riservatezza dei dati (costi, margini, clienti verso un fornitore di modelli), permessi per ruolo da replicare e testo libero come veicolo di istruzioni. Non si riapre senza una nuova richiesta.
