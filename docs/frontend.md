# Frontend

Applicazione web in **React + TypeScript** (Vite), con **Tailwind CSS**, React Router e TanStack Query. In sviluppo le chiamate `/api` passano dal proxy di Vite verso il backend locale.

> Stato: **passo 8a** (accesso, struttura, elenco e dettaglio dei CE in sola lettura, vista del viewer). Seguono 8b (modifica del CE e workflow), 8c (dashboard) e 8d (amministrazione).

## Avvio in locale
```bash
make install                  # dipendenze di backend e frontend
make db && make migrate && make seed
make backend                  # http://localhost:8000  (serve BOOTSTRAP_ADMIN_EMAIL in backend/.env)
make demo                     # carica clienti, collaboratori e 8 CE di esempio (in un altro terminale)
make frontend                 # http://localhost:5173
```
Entra con l'**accesso di sviluppo** (compare solo in locale): `admin@huware.com`, `anna.presale@huware.com`, `paolo.presale@huware.com` oppure `vera.viewer@huware.com` (viewer). L'accesso reale con Google richiede `VITE_GOOGLE_CLIENT_ID` in `frontend/.env.local`.

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

## Ruoli
| Ruolo | Cosa vede |
|---|---|
| admin, presale | elenco completo con stato, autore, prezzo e margine; dettaglio con indicatori, fasi e righe, riepilogo, staffing, versioni, storico; tutti gli export |
| viewer | solo i CE approvati: codice, cliente, progetto, periodo, versione e prezzo; dettaglio con giornate e ricavi per fase; export del solo riepilogo |

Il viewer non riceve mai costi o righe: lo garantisce il **backend** (schemi dedicati), non il frontend, e un test nel browser lo verifica leggendo tutte le risposte dell'API che il viewer riceve.

## Come è fatto
- `src/api/schema.d.ts` è **generato** dallo schema OpenAPI del backend (`frontend/openapi.json`). Dopo ogni modifica alle API: `make api-types`. La CI controlla che siano aggiornati.
- Il token di sessione sta in `sessionStorage` (si perde alla chiusura della scheda). Un `401` dell'API chiude la sessione e riporta al login con un avviso.
- I filtri dell'elenco stanno nell'indirizzo (`/ce?status=approved&code=beta`): si possono condividere e sopravvivono al ricaricamento.
- I file (Excel, PDF, CSV) si scaricano con una chiamata autenticata, non con un semplice link.
- Accessibilità: struttura semantica, etichette su tutti i campi, tabelle larghe che scorrono **anche con la tastiera**, link "Vai al contenuto", focus visibile. Le pagine sono controllate in automatico con axe (WCAG 2 A e AA).
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
```
I test nel browser girano su due formati (desktop 1280 px e smartphone 390 px) e coprono accesso, sessione scaduta, filtri, esportazioni, dettaglio, vista del viewer, assenza di scorrimento orizzontale e accessibilità.

## Limiti noti
- L'accesso con Google non è ancora stato provato con un Client ID vero.
- I campi data mostrano il formato del browser (`gg/mm/aaaa` sui browser in italiano).
- Il frontend non ha ancora la modifica dei CE né le dashboard e l'amministrazione (passi 8b, 8c, 8d).
