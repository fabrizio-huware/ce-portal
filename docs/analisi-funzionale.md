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
- **Profilo (listino)**: nome, prezzo/giorno, costo/giorno, anno di validità. Gestito dall'admin. Banda e billability target facoltativi, non usati nei calcoli.
- **CE Testata**: codice progetto (univoco, manuale), progetto, cliente, SF Opp, Business Unit, note, data inizio, data fine, stato, modalità di pianificazione, prezzo firmato, versione, autore.
- **CE Fase**: nome, % di contingency.
- **CE Riga**: fase, attività, profilo, collaboratore (facoltativo), flag "Project Management", ore oppure % mensili. Righe esterne con costo e ricavo liberi.
- **Di supporto**: calendario festività e chiusure aziendali (admin), milestone, versioni CE, audit log.

## 4. Regole funzionali
- Modalità di pianificazione unica per CE: ore dirette oppure % mensile.
- Durata massima 12 mesi.
- Giorni lavorativi = lun-ven esclusi festivi e chiusure del calendario admin (sede Milano). 1 giorno = 8 ore.
- Modalità % mensile: % per riga e per mese, da 0 a 100%, applicata ai giorni lavorativi del mese; mesi parziali in pro-rata sui giorni lavorativi effettivi. Esplosione automatica in FTE, giorni e ore (come "Staffing mensilizzato").
- Modalità ore dirette: ore ripartite sui mesi in proporzione ai giorni lavorativi tra inizio e fine progetto.
- Prezzi e costi sempre dal profilo, congelati nel CE alla creazione; nessun override per riga; l'admin può riallineare al listino.
- Righe esterne: costo e ricavo liberi, senza profilo. Fondi/PSF esclusi.
- Contingency per fase.
- Milestone opzionali, come etichette sui mesi.
- Workflow: Bozza → In approvazione → Approvato / Rifiutato. Una modifica a un CE approvato crea una nuova versione in Bozza, con storico consultabile e approvazione da rifare.
- Duplicazione CE; cancellazione logica solo admin.
- Audit log delle modifiche; backup automatici.

## 5. Formule (da validare allo Step 4)
Considerate acquisite:
- Costo riga = giorni × costo/giorno; Ricavo riga = giorni × prezzo/giorno.
- Margine € = Ricavi − Costi; Margine % = Margine ÷ Ricavi; C/R = Costi ÷ Ricavi.
- GG Project Management = giorni delle righe con flag; GG Delivery = altre righe interne; GG Totali = somma.
- Prezzo progetto = somma ricavi, contingency inclusa. Margine "firmato" calcolato sul prezzo progetto firmato (campo manuale).

Da validare con numeri reali:
- Contingency: ipotesi ricavo = % × ricavi della fase, costo zero.
- Prezzo vendita min, Max sconto, Fee media min firmato: ipotesi basata su soglia minima di margine % impostata dall'admin.
- Le righe esterne non contano nelle giornate.

## 6. Dashboard, ricerca, export, notifiche
- Dashboard: scheda KPI del CE; portfolio CE (margine per cliente e periodo); carico risorse per mese, collaboratore e profilo (su CE approvati).
- Ricerca: cliente, progetto, codice, date (da-a), stato, autore.
- Export: Excel, CSV, PDF con logo.
- Email via Mailjet da teamdata@huware.com: CE inviato in approvazione → admin; CE approvato/rifiutato → autore; nuovo utente abilitato → utente.

## 7. Aspetti tecnici
Backend FastAPI (OpenAPI), frontend React + TypeScript responsive in italiano (EUR), PostgreSQL su Cloud SQL, Cloud Run con 2 ambienti (test, prod) in progetti separati, regione europe-west8, URL Cloud Run, monorepo GitHub con GitHub Actions. Design ispirato a huware.com (palette e font da validare nello Step 8). Campi per ID esterni predisposti per Jira e NetSuite.

## 8. Fuori ambito (per ora)
Override tariffe per riga, Fondi/PSF, campi Monday/Partners/EST, integrazioni Jira e NetSuite.
