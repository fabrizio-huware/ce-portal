# Analisi funzionale (v1.0 – approvata)

## 1. Obiettivo
Portale interno per creare, memorizzare, modificare e ricercare i Conti Economici (CE) di progetto, con calcolo di costi, ricavi, margini e impegno delle risorse. L'approvazione dei CE è riservata all'admin.

## 2. Ruoli e permessi

| Funzione | Admin | Presale | Viewer |
|---|---|---|---|
| Gestione utenti, listini, calendario, anagrafiche | sì | no | no |
| Creare / duplicare CE | sì | sì | no |
| Modificare CE | tutti | solo i propri | no |
| Inviare in approvazione | sì | sì | no |
| Approvare (sempre, anche da Bozza) | sì | no | no |
| Eliminare CE (cancellazione logica) | sì | no | no |
| Cercare e visualizzare CE | tutti, vista completa | tutti, vista completa | solo CE approvati, vista riassuntiva |

**Vista riassuntiva del viewer**: giornate di Management, giornate di Delivery, ricavi per fase, totale generale. Nessun costo, margine, staffing o dettaglio righe. Gli export rispettano la stessa visibilità. Il viewer non accede alle dashboard portfolio e carico risorse.

## 3. Entità
- **Utente**: email Google, ruolo, attivo/non attivo. Registrato dall'admin; login Google limitato al dominio huware.com.
- **Cliente**: ragione sociale, indirizzo. Creabile da admin e presale.
- **Collaboratore**: nome, cognome, profilo di default, attivo/non attivo. Anagrafica separata dagli utenti; import CSV iniziale.
- **Profilo (listino)**: nome, prezzo/giorno, costo/giorno, anno di validità, indicatore "esterno" (profilo **Esterni**, che confluisce in Servizi Esterni). Gestito dall'admin. Banda e billability target facoltativi, non usati nei calcoli.
- **CE Testata**: codice progetto (univoco, manuale), progetto, cliente, SF Opp, Business Unit, note, data inizio, data fine, stato, modalità di pianificazione, **max sconto %** (inserito da chi compila), prezzo firmato, versione, autore.
- **CE Fase**: nome, % di contingency.
- **CE Riga**: fase, attività, profilo (anche "Esterni"), collaboratore (facoltativo), flag "Project Management", ore oppure % mensili.
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
- Dashboard: scheda KPI del CE; portfolio CE (margine per cliente e periodo); carico risorse per mese, collaboratore e profilo (su CE approvati).
- Ricerca: cliente, progetto, codice, date (da-a), stato, autore.
- Export: Excel, CSV, PDF con logo.
- Email via Mailjet da teamdata@huware.com: CE inviato in approvazione → admin; CE approvato/rifiutato → autore; nuovo utente abilitato → utente.

## 7. Aspetti tecnici
Backend FastAPI (OpenAPI), frontend React + TypeScript responsive in italiano (EUR), PostgreSQL su Cloud SQL, Cloud Run con 2 ambienti (test, prod) in progetti separati, regione europe-west8, URL Cloud Run, monorepo GitHub con GitHub Actions. Design ispirato a huware.com (palette e font da validare nello Step 8). Campi per ID esterni predisposti per Jira e NetSuite.

## 8. Fuori ambito (per ora)
Override tariffe per riga, Fondi/PSF, campi Monday/Partners/EST, integrazioni Jira e NetSuite.
