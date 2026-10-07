# Frontend

Applicazione web in **React + TypeScript** (Vite), con **Tailwind CSS**, React Router e TanStack Query. In sviluppo le chiamate `/api` passano dal proxy di Vite verso il backend locale.

> Stato: **passi 8a, 8b e 8c** (accesso, elenco, dettaglio, vista del viewer, creazione e modifica dei CE con flusso di approvazione, **dashboard**). Segue 8d (amministrazione).

## Avvio in locale
```bash
make install                  # dipendenze di backend e frontend
make db && make migrate && make seed
make backend                  # http://localhost:8000  (serve BOOTSTRAP_ADMIN_EMAIL in backend/.env)
make demo                     # carica clienti, collaboratori e 8 CE di esempio (in un altro terminale)
                              # entra con l'admin di BOOTSTRAP_ADMIN_EMAIL; se è un'altra: DEMO_ADMIN_EMAIL=tua@email make demo
make frontend                 # http://localhost:5173
```
Entra con l'**accesso di sviluppo** (compare solo in locale): la **tua email di amministratore** (quella in `BOOTSTRAP_ADMIN_EMAIL`), oppure gli utenti di esempio creati da `make demo`: `anna.presale@huware.com`, `paolo.presale@huware.com` (presale) e `vera.viewer@huware.com` (viewer). L'accesso reale con Google richiede `VITE_GOOGLE_CLIENT_ID` in `frontend/.env.local`.

## Variabili d'ambiente (`frontend/.env.example`)
| Variabile | Significato |
|---|---|
| `VITE_API_BASE_URL` | indirizzo base delle API; vuoto = stessa origine (proxy o web server) |
| `VITE_GOOGLE_CLIENT_ID` | Client ID OAuth di Google per l'accesso reale |
| `VITE_ENABLE_DEV_LOGIN` | `true` solo in sviluppo: accesso simulato senza Google. **Mai in produzione**: la compilazione di produzione lo ignora per scelta, perché il backend lo rifiuta comunque fuori da `APP_ENV=local` |

## Grafica
- **Colori del brand**: bianco, nero, ciano `#00f5fe`, turchese `#00acc7`. Il ciano si usa come **evidenziatore** (testo nero su ciano, come nel sito Huware) e il turchese per gli accenti; per testi e link colorati c'è `teal-700`, una tonalità scurita del turchese, perché il ciano su bianco non è leggibile. Vedi `tailwind.config.ts`.
- **Font**: **DM Sans** (identificato per confronto visivo con lo screenshot del sito), pesi Light per i titoli e Medium per l'interfaccia, con lettere leggermente strette nei titoli. È **incluso nel portale** (`@fontsource-variable/dm-sans`, licenza OFL): nessuna chiamata a Google Fonts, quindi nessun trasferimento di dati dei visitatori (GDPR).
- **Logo**: `public/brand/logo-black.png` e `logo-white.png` (sfondo trasparente). La risoluzione è modesta (410 px): sostituire con un SVG appena disponibile. `backend/app/assets/logo.png` è lo stesso logo, usato nei PDF.
- Cifre a larghezza uguale (`tnum`) e importi che non vanno a capo, per leggere bene le colonne.

## Come si compila un CE
1. **Nuovo CE** (`/ce/nuovo`): codice, cliente (se non c'è, «+ Nuovo» lo crea senza lasciare il modulo), progetto, periodo (al massimo 12 mesi), pianificazione **a ore** o **a percentuali mensili**. Parte con le fasi standard, se vuoi.
2. **Editor** (`/ce/:id/modifica`, pulsante «Modifica» nel dettaglio):
   - *Dati generali*: cliente, progetto, periodo, business unit, opportunità Salesforce, max sconto, prezzo firmato. Cambiare la modalità non cancella nulla: ore e percentuali restano in bozza e si inviano solo quelle della modalità scelta.
   - *Fasi e righe*: ogni fase ha nome e contingency; ogni riga ha attività, profilo, collaboratore, flag PM e le **ore** (oppure una **percentuale per ogni mese**). Se scegli un collaboratore su una riga senza profilo, si propone il suo profilo.
   - *Giorni non lavorativi*: per mese; lasciando vuoto vale il calendario generale (il valore proposto compare nel campo).
   - *Milestone e note*.
3. **Totali in tempo reale**: in alto compaiono prezzo, margine, costi e giornate, e ogni riga mostra giorni, ricavo e costo. Li **calcola il server** con lo stesso motore del salvataggio (`POST /ce/{id}/calculate`), quindi non possono differire da quelli salvati. Se i dati sono incompleti, l'anteprima lo dice e il calcolo riparte appena li completi.
4. **Salvataggio** con «Salva» o Ctrl/⌘+S. Il salvataggio è manuale: finché non salvi, nulla cambia sul server. Il pulsante «Annulla modifiche» riporta allo stato salvato.
   - Se qualcuno ha modificato il CE nel frattempo, **non si sovrascrive nulla**: si avvisa e si può ricaricare l'ultima versione.
   - Uscendo con modifiche non salvate (link, indietro del browser o chiusura della scheda) compare un avviso.

**Scorciatoie**: Invio scende alla riga sotto nella stessa colonna (Maiusc+Invio sale). Puoi **incollare da Excel** un blocco di celle: in una colonna di ore riempie le righe successive della fase; nelle percentuali riempie righe e mesi. Un valore non numerico si inserisce comunque, e resta evidenziato come errore. Nei numeri valgono virgola e punto: `12,5`, `12.5`, `1.234,5`.

**Flusso di approvazione** (dal dettaglio; si vede solo ciò che il server consente):

| Azione | Chi | Effetto |
|---|---|---|
| Invia in approvazione | autore o admin | l'admin riceve un'email; il CE non si modifica finché è in approvazione |
| Ritira | autore o admin | torna in bozza |
| Approva / Rifiuta (con motivo) | admin | l'autore riceve un'email; da approvato non si modifica |
| Nuova versione | chi può modificare | copia il CE approvato e apre l'editor |
| Scarta la versione in lavorazione | chi può modificare | si torna all'ultima approvata |
| Riallinea tariffe e calendario | admin | aggiorna ai valori correnti |
| Duplica come nuovo CE | tutti gli editor | copia struttura e righe in un nuovo codice |
| Elimina | admin | cancellazione logica |

Se un CE non è inviabile, l'elenco completo dei problemi compare nella finestra di conferma.

## Dashboard (solo admin e presale)
La voce «Dashboard» del menu apre due pagine; i filtri stanno nell'indirizzo (si possono condividere) e ogni pagina si esporta in Excel e CSV. Le regole di calcolo sono in [dashboard.md](dashboard.md).

**Portfolio** (`/dashboard/portfolio`): indicatori (ricavi, margine e giornate degli approvati, pipeline a parte), **ricavi per mese** (barre impilate: nero = approvati, ciano tratteggiato = pipeline), ricavi per cliente e per business unit, conteggio per stato, elenco dei CE con link al dettaglio. Filtri: periodo, cliente, business unit, «Includi la pipeline» (attivo di default). La vista per mese non include la contingency e lo dice.

**Carico risorse** (`/dashboard/risorse`): per ogni collaboratore una riga con l'impegno **mese per mese** in percentuale (100% = una persona a tempo pieno sui giorni lavorativi del calendario generale). Le celle oltre il 100% sono rosse con il simbolo ⚠ e il numero: il colore non è mai l'unica informazione. Sotto, le giornate per profilo e quelle non assegnate a una persona. Filtri: periodo (mesi), cliente, profilo, collaboratore, «Includi la pipeline» (spento di default); senza date, dal mese corrente a 11 mesi dopo.

I grafici sono semplici e senza librerie. Ogni grafico ha una **tabella equivalente per i lettori di schermo**, una legenda con i nomi delle serie e i valori scritti; le tabelle larghe scorrono anche con la tastiera. Il disegno nasconde il grafico ai lettori di schermo per non ripeterlo.

## Ruoli
| Ruolo | Cosa vede |
|---|---|
| admin, presale | **dashboard**; elenco completo con stato, autore, prezzo e margine; dettaglio con indicatori, fasi e righe, riepilogo, staffing, versioni, storico; tutti gli export |
| viewer | solo i CE approvati: codice, cliente, progetto, periodo, versione e prezzo; dettaglio con giornate e ricavi per fase; export del solo riepilogo |

Il viewer non riceve mai costi o righe: lo garantisce il **backend** (schemi dedicati), non il frontend, e un test nel browser lo verifica leggendo tutte le risposte dell'API che il viewer riceve.

## Come è fatto
- `src/api/schema.d.ts` è **generato** dallo schema OpenAPI del backend (`frontend/openapi.json`). Dopo ogni modifica alle API: `make api-types`. La CI controlla che siano aggiornati.
- Il token di sessione sta in `sessionStorage` (si perde alla chiusura della scheda). Un `401` dell'API chiude la sessione e riporta al login con un avviso.
- I filtri dell'elenco stanno nell'indirizzo (`/ce?status=approved&code=beta`): si possono condividere e sopravvivono al ricaricamento.
- I file (Excel, PDF, CSV) si scaricano con una chiamata autenticata, non con un semplice link.
- Accessibilità: struttura semantica, etichette su tutti i campi, tabelle larghe che scorrono **anche con la tastiera**, link "Vai al contenuto", focus visibile. Le pagine sono controllate in automatico con axe (WCAG 2 A e AA).
- Le finestre di dialogo usano l'elemento `<dialog>` nativo e sono disegnate fuori dal contenuto (`createPortal`), così un modulo non ne contiene mai un altro; ognuna reagisce solo alla propria chiusura.
- I contenitori che scorrono in orizzontale sono `relative`: i testi «solo per lettori di schermo» (posizionati in modo assoluto) altrimenti sfuggirebbero al taglio e allargherebbero la pagina su smartphone.
- Responsive: sotto i 768 px l'elenco diventa una lista di schede, i filtri stanno dietro al pulsante "Filtri" e il menu diventa a tendina.

## Test
```bash
cd frontend
npm run lint            # controllo dei tipi
npm test                # test unitari (formati, errori, sessione, download, componenti, pagine)
```
**Test nel browser** (Playwright): servono il backend con `make demo` e il frontend compilato in modalità sviluppo.
```bash
npx playwright install chromium        # una sola volta
npm run build:dev && npm run preview   # in un terminale (porta 4173)
npm run test:e2e                       # in un altro
E2E_SCREENSHOTS=1 npx playwright test e2e/screenshots.spec.ts   # schermate in e2e/screens/
# se l'admin del tuo database non è admin@huware.com:  E2E_ADMIN_EMAIL=tua@email npm run test:e2e
```
Prima di ogni esecuzione i test eliminano da soli i CE di prova rimasti (codice `PS-E2E…`) e ognuno ripulisce ciò che crea.

I test nel browser girano su due formati (desktop 1280 px e smartphone 390 px) e coprono accesso, sessione scaduta, filtri, esportazioni, dettaglio, vista del viewer, creazione e modifica (ore, percentuali, incolla da Excel, conflitti, modifiche non salvate), flusso di approvazione, permessi, assenza di scorrimento orizzontale e accessibilità.

## Limiti noti
- L'accesso con Google non è ancora stato provato con un Client ID vero.
- I campi data mostrano il formato del browser (`gg/mm/aaaa` sui browser in italiano).
- Non c'è ancora un pulsante per **ripristinare un CE eliminato** (esiste l'API) né il salvataggio automatico: si salva a mano.
- Su smartphone la griglia di modifica scorre in orizzontale (c'è un suggerimento); per compilare molte righe è più comodo un computer.
- L'anteprima dei totali richiede dati completi: finché un campo obbligatorio manca o ha un numero non valido, i totali restano quelli dell'ultimo calcolo.
- Mancano ancora l'amministrazione di utenti, clienti, collaboratori, listino, calendario ed email (passo 8d).
- I grafici sono barre semplici: niente zoom, filtri sul grafico o confronto fra periodi. Nelle barre per cliente e business unit si mostrano i primi 8, gli altri sono raggruppati in «Altri».
