# Guida all'uso del Portale Conti Economici

Per chi usa il portale ogni giorno: **presale** (creano e compilano i CE), **amministratori** (approvano e gestiscono i dati di base) e **viewer** (consultano i CE approvati). Per le regole di calcolo complete c'è [formule.md](formule.md); per l'analisi funzionale [analisi-funzionale.md](analisi-funzionale.md).

## Chi può fare cosa

| | Amministratore | Presale | Viewer |
|---|---|---|---|
| Vedere i CE | tutti, con costi e margini | tutti, con costi e margini | solo gli **approvati**, in vista riassuntiva |
| Creare e duplicare CE | sì | sì | no |
| Modificare un CE | tutti | **solo i propri** | no |
| Inviare in approvazione | sì | sì | no |
| Approvare, rifiutare, riallineare, eliminare | sì | no | no |
| Dashboard | sì | sì | no |
| Amministrazione (utenti, listino, calendario, email…) | sì | no | no |

Il **viewer** vede codice, cliente, progetto, date, giornate di Management e di Delivery, ricavi per fase e totale. **Non** vede mai costi, margini, ore, righe o tariffe, in nessuna schermata né in nessun file esportato.

## Accedere

1. Apri l'indirizzo del portale e premi **«Accedi con Google»**, con il tuo account `@huware.com`.
2. Se vedi **«Utente non abilitato»**: il tuo account non è ancora registrato. Chiedi a un amministratore di aggiungerti (*Amministrazione → Utenti*): riceverai un'email.
3. La sessione dura **al massimo 8 ore** e finisce comunque se chiudi la scheda o premi **Esci**. Quando scade il portale te lo dice e ti riporta all'accesso: ripeti «Accedi con Google» (le modifiche non salvate vanno perse, quindi salva spesso).

## Trovare un conto economico

Nell'elenco puoi filtrare per **codice**, **progetto**, **cliente**, **stato**, **periodo** (mostra i progetti *attivi* nel periodo indicato) e **«Solo i miei CE»**. Su smartphone i filtri stanno dietro il pulsante **Filtri**. **«Esporta elenco»** scarica ciò che vedi con i filtri attivi.

Gli stati sono: **Bozza** → **In approvazione** → **Approvato** oppure **Rifiutato**. Accanto allo stato c'è il numero della versione (v1, v2…).

## Creare un CE

**«+ Nuovo CE»**, poi compili:

- **Codice** del CE (per esempio `PS-CLIENTE-PROGETTO-PJT`): deve essere **unico**; si scrive in maiuscolo.
- **Cliente**: sceglilo dall'elenco, oppure **«+ Nuovo»** per crearne uno senza uscire.
- **Nome del progetto** e **periodo** (inizio e fine, **al massimo 12 mesi**).
- **Come pianifichi le attività**:
  - **A ore**: scrivi le ore di ogni riga; il portale le distribuisce sui mesi in proporzione ai giorni lavorativi. È la scelta più semplice.
  - **A percentuali mensili**: per ogni riga indichi la % di impegno di ogni mese. Conviene quando conosci l'impegno mese per mese.
- Facoltativi: business unit, opportunità Salesforce, max sconto.
- **«Parti dalle fasi standard»** crea le fasi del foglio (solo i nomi, vuote).

Alla creazione il CE **copia le tariffe del listino dell'anno di inizio**: se per quell'anno non c'è il listino, il portale lo dice e un amministratore deve prima caricarlo.

## Compilare un CE (l'editor)

Si apre con **Modifica** nel dettaglio (o subito dopo aver creato il CE).

**In alto** vedi sempre i totali: **Prezzo progetto**, **Margine** (in € e in %), **Costi**, **Giornate**. Si aggiornano mentre scrivi e li calcola il server con le stesse regole del salvataggio. Se un dato manca o è sbagliato, il messaggio sotto i totali dice di completare i dati.

**Dati generali**: cliente, progetto, periodo, pianificazione, business unit, Salesforce, **Max sconto %** e **Prezzo firmato (€)**. Cambiare la pianificazione da ore a percentuali non cancella nulla: le due serie di dati restano in bozza e si salva solo quella scelta.

**Fasi e righe**:
- Ogni **fase** ha un nome e una **Contingency %**: aumenta i **ricavi** della fase di quella percentuale, **senza aggiungere costi**.
- Ogni **riga** ha, nell'ordine: **Attività**, **Collaboratore** (facoltativo), **Profilo**, la casella **PM** (Project Management) e le **ore** o le **% mensili**. Conviene scegliere **prima il collaboratore**: il **profilo si carica da solo** con quello di default dell'anagrafica e **segue sempre il collaboratore**, anche se lo avevi cambiato a mano; poi lo puoi modificare liberamente. Togliendo il collaboratore il profilo resta com'è. Se il profilo di default del collaboratore **non ha la tariffa dell'anno del CE**, la riga conserva il profilo che aveva e compare una nota (per esempio «non ha la tariffa 2026: scegli il profilo»), che sparisce quando scegli il profilo.
- Per ogni riga vedi **Giorni**, **Ricavo** e **Costo**, e in fondo alla fase il **totale**. Il menu **⋯** di riga permette di spostare su e giù, duplicare, eliminare; quello di fase di spostare ed eliminare la fase.
- I profili **senza tariffa per l'anno del CE** sono segnalati e non si possono scegliere.
- Il profilo **Esterni** serve per i servizi esterni (stessa regola degli altri, con la tariffa del listino).

**Giorni non lavorativi per mese** (sezione richiudibile): per ogni mese puoi indicare quanti giorni feriali non si lavora (festività, chiusure). **Se lasci vuoto vale il calendario generale** (il valore proposto compare nel campo). Questi valori restano **congelati nel CE**: se l'amministratore cambia il calendario dopo, i CE esistenti non cambiano.

**Milestone e note**: etichette sui mesi e note interne.

### Scorciatoie
- **Invio** scende alla riga sotto nella stessa colonna; **Maiusc+Invio** sale.
- **Incolla da Excel**: copia una colonna di ore (o un blocco di percentuali) e incollalo nella prima cella: riempie le righe successive. Vanno bene virgola e punto decimali (`12,5`, `1.234,5`). Un valore non numerico si inserisce comunque e resta evidenziato come errore.
- **Ctrl+S** (⌘+S su Mac) salva.

### Salvare, annullare, uscire
- Il salvataggio è **manuale**: finché non premi **Salva**, nulla cambia sul server. In basso vedi «Modifiche non salvate» oppure «Tutto salvato».
- **Annulla modifiche** riporta allo stato salvato.
- Se esci con modifiche non salvate compare un **avviso**.
- Se nel frattempo **qualcun altro ha modificato lo stesso CE**, il portale lo segnala e **non sovrascrive** il suo lavoro: devi ricaricare l'ultima versione (le tue modifiche andrebbero perse, quindi copiale prima).
- Prima di salvare il portale elenca i punti da correggere (attività mancante, profilo non scelto, numero non valido…).

## Capire i numeri

| Voce | Significato |
|---|---|
| **Giornate** | ore ÷ 8. «Totali» sono le giornate di base (senza contingency), esterni compresi |
| **Ricavi / Costi** | giorni × prezzo (o costo) giornaliero del profilo |
| **Prezzo progetto** | ricavi interni + esterni + ricavo da contingency |
| **Margine** | ricavi − costi; **Margine %** = margine ÷ ricavi |
| **Prezzo di vendita minimo** | prezzo progetto × (1 − max sconto) |
| **Fee media minima** | prezzo di vendita minimo ÷ giornate totali |
| **Con prezzo firmato** | margine = firmato − costi; margine % e C/R calcolati sul firmato |
| **FTE** (nel carico risorse) | giorni del mese ÷ giorni lavorativi del mese; 100% = una persona a tempo pieno |

Gli importi finali sono arrotondati al centesimo; la somma di voci arrotondate può scostarsi di 1 centesimo dal totale, che è quello esatto. Le formule complete e il confronto col foglio sono in [formule.md](formule.md).

## Il flusso di approvazione

Dal dettaglio del CE compaiono **solo** le azioni che puoi fare in quello stato.

| Azione | Chi | Cosa succede |
|---|---|---|
| **Invia in approvazione** | autore o admin | il CE è bloccato per il presale; gli amministratori ricevono un'email. Se il CE non è completo, **si vede l'elenco dei problemi** e non parte |
| **Ritira** | autore o admin | torna in bozza |
| **Approva** | admin | l'autore riceve un'email; il CE non si modifica più. Un admin può approvare anche una bozza |
| **Rifiuta** | admin | serve un **motivo**; l'autore lo riceve per email e lo vede nel CE; poi può correggere e reinviare |
| **Nuova versione** | chi può modificare | copia il CE approvato in una nuova bozza (righe, tariffe e calendario compresi); gli amministratori ricevono un'email. Il viewer continua a vedere l'ultima versione **approvata** finché la nuova non è approvata |
| **Scarta la versione in lavorazione** | chi può modificare | torna all'ultima versione approvata |
| **Duplica come nuovo CE** | tutti gli editor | nuovo codice, stesse fasi e righe, con tariffe e calendario **correnti** (non copia max sconto, prezzo firmato, Salesforce e note) |
| **Riallinea tariffe e calendario** | admin | aggiorna una versione non approvata ai valori correnti |
| **Elimina** | admin | scompare dagli elenchi; si ripristina da *Amministrazione → CE eliminati* |

Le schede **Versioni** e **Storico** del dettaglio mostrano tutte le versioni e chi ha fatto cosa e quando. **Nelle email compare solo il prezzo, mai costi o margini.**

## Esportare

Dal dettaglio, **Esporta**:
- **Excel completo**: con le **formule vere**. Le celle blu sono modificabili per fare simulazioni (per esempio cambiare ore o tariffe) e i totali si ricalcolano. Fogli: Riepilogo, Dettaglio, Fasi, Profili, Staffing mensile, Tariffe, Note.
- **Riepilogo** (Excel, PDF, CSV): senza costi né margini, adatto a condividere. **È l'unica variante per il viewer.**
- **PDF completo**: pagina orizzontale per uso interno, con il logo.
- **CSV**: pensato per Excel italiano (punto e virgola, virgola decimale).

Ogni esportazione viene registrata.

## Le dashboard (admin e presale)

**Portfolio**: ricavi, margine e giornate dei CE **approvati**, con la **pipeline** (bozze e in approvazione di CE ancora senza versione approvata) mostrata a parte. Il grafico per mese usa il **nero per gli approvati** e il **tratteggio ciano per la pipeline**; la vista per mese non include la contingency. Filtri: periodo, cliente, business unit, «Includi la pipeline». Un avviso segnala i CE approvati che hanno una nuova versione in lavorazione: conta ancora la versione approvata.

**Carico risorse**: per ogni collaboratore l'impegno mese per mese in %, sui giorni lavorativi del calendario generale. Sopra la tabella **«Mostra nelle celle»** sceglie cosa vedere: **Entrambi** (predefinito: la percentuale in evidenza e sotto i giorni, per esempio «54%» e «10,8 gg»), solo **Percentuale**, solo **Giorni** oppure solo **Ore**. Le **ore** sono i giorni × 8 e le calcola il server (per esempio 2,6 giorni sono `20,8` ore). Giorni e ore sono con un decimale, arrotondati da 5 in su come in Excel; il **totale a destra** e la riga «Giorni lavorativi del mese» **restano in giorni** in ogni modalità, con due decimali il totale. La scelta resta nell'indirizzo della pagina, quindi si conserva ricaricando e condividendo il link. Le celle **oltre il 100%** sono rosse con ⚠ e il numero (in tutte e tre le modalità). Di default considera **solo gli approvati**; con «Includi la pipeline» vedi cosa succederebbe se andasse tutto in porto. Sotto ci sono le giornate per profilo. Senza date, mostra dal mese corrente a 11 mesi dopo.

Entrambe si esportano in Excel e CSV, e i filtri restano nell'indirizzo: puoi condividere il link.

## Per gli amministratori

La voce **Amministrazione** ha sette schede. Utenti, clienti, collaboratori e profili **non si eliminano: si disattivano** (i dati storici restano).

| Scheda | Cosa si fa |
|---|---|
| **Utenti** | aggiungi (la persona riceve un'email), cambia il ruolo, attiva e disattiva. Non si può togliere il ruolo o l'accesso all'**ultimo** admin attivo |
| **Clienti** | crea, modifica, disattiva. Un cliente disattivato **non si può scegliere in un CE nuovo**, ma resta nei CE esistenti (che si aprono e si salvano normalmente, con la dicitura «(disattivato)») e tra i filtri dell'elenco, per poter cercare i CE passati |
| **Collaboratori** | anagrafica con profilo di default, ID NetSuite e Jira (facoltativi). **Importa da CSV** |
| **Listino** | profili e **tariffe per anno** (prezzo e costo al giorno). **Importa da CSV**. Una modifica vale per i CE **nuovi**; per aggiornare uno esistente si usa «Riallinea» |
| **Calendario** | «Genera le festività» dell'anno (ripetibile senza duplicare), chiusure aziendali (a mano o da CSV) |
| **Email** | stato di ogni email, errori, «Riprova», «Invia subito quelle in coda», «Invia un'email di prova a me» |
| **CE eliminati** | elenco e **ripristino** |

### Importare da CSV
Si sceglie il file e si preme **«Controlla il file»**: **nulla viene scritto** finché non confermi con **«Importa»**. Il controllo dice quante righe saranno nuove, aggiornate o invariate. **Se anche una sola riga è sbagliata non si importa nulla**, e gli errori sono elencati per numero di riga. Separatore `;`, UTF-8, al massimo 5000 righe. Dalla finestra si scarica un file di esempio.

| Cosa | Colonne |
|---|---|
| Collaboratori | `Nome; Cognome; Profilo; Attivo` (facoltative: `netsuite_id`, `jira_account_id`). Il profilo deve esistere ed essere attivo |
| Listino | `Profilo; Anno; Prezzo giorno; Costo giorno`. Crea i profili mancanti e la tariffa dell'anno |
| Chiusure aziendali | `Data` (gg/mm/aaaa); `Descrizione` (facoltativa). Le date già presenti restano come sono |

### Cose che si fanno spesso
- **Nuovo anno**: carica il listino del nuovo anno **prima** che si creino CE che iniziano in quell'anno, genera le festività e inserisci le chiusure. Vedi [manutenzione.md](manutenzione.md).
- **Nuova persona**: aggiungila come **utente** (se deve accedere) e come **collaboratore** (se compare nei CE). Sono due anagrafiche separate.
- **Una persona lascia l'azienda**: disattiva utente e collaboratore. I CE passati restano com'erano.
- **Cambia una tariffa**: aggiorna il listino dell'anno; i CE esistenti non cambiano finché non li riallinei.

## Se qualcosa non va

| Cosa vedi | Cosa significa e cosa fare |
|---|---|
| «Utente non abilitato» all'accesso | il tuo account non è registrato: chiedi a un amministratore |
| Non trovi il pulsante **Modifica** | il CE è approvato o in approvazione, oppure non è tuo. Il messaggio nell'editor lo spiega. Per cambiare un approvato: **Nuova versione** |
| «Il CE non è inviabile» | nella finestra c'è l'elenco dei problemi (righe senza ore, dati mancanti…): correggi e riprova |
| Un profilo è «senza tariffa 2027» | manca il listino di quell'anno: chiedi all'amministratore |
| I totali in alto non si aggiornano | un campo obbligatorio manca o ha un numero non valido: guarda il messaggio sotto i totali |
| «Il CE è stato modificato da qualcun altro» | non hai sovrascritto nulla; ricarica l'ultima versione |
| Una pagina impiega qualche secondo al primo accesso della giornata | il servizio si "sveglia" dopo una pausa; poi è rapido |
| Una email non arriva | controlla lo spam; un amministratore può vedere lo stato in *Amministrazione → Email* e premere «Riprova» |
| Un file Excel esportato non si apre come previsto | prova il CSV, oppure il riepilogo; segnala l'esempio a chi amministra |
