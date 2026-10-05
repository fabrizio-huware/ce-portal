# Formule del motore di calcolo

Il motore è nel modulo `backend/app/engine` ed è **isolato**: non usa il database, riceve dati semplici e restituisce numeri. Tutti i valori sono `Decimal` (mai virgola mobile).

Le formule replicano il foglio reale *PS-BONGA-AI-PJT - CE di progetto* e sono state validate confrontando il motore con il foglio (vedi "Validazione" in fondo).

## Convenzioni
- 1 giorno = 8 ore. Settimane = giornate ÷ 5.
- **Nessun arrotondamento nei passaggi intermedi.** Gli importi finali sono arrotondati al centesimo (mezzo centesimo per eccesso); giorni e ore a 5 decimali; le percentuali sono frazioni a 6 decimali (0,571694 = 57,17%).
- Conseguenza: la somma di voci arrotondate (per esempio i ricavi mensili) può scostarsi di 1 centesimo dal totale, che è quello esatto, come nel foglio.
- Se il denominatore è zero (ricavi nulli, nessuna giornata) il risultato è `None`, mostrato come "n/d": mai uno 0% fittizio.

## Giorni lavorativi del mese
`giorni lavorativi = giorni lun-ven del mese intero − giorni non lavorativi inseriti sul CE`

Foglio: `NETWORKDAYS.INTL(inizio mese; fine mese; 1) − NO-WORK DAYS` (riga 12-13 di "Allocazione %"). I mesi del progetto vanno dal mese della data di inizio al mese della data di fine, **interi** (nessun pro-rata). Massimo 12 mesi.

## Righe
| Grandezza | Formula | Foglio |
|---|---|---|
| Giorni (modalità ore) | ore ÷ 8, ripartiti sui mesi in proporzione ai giorni lavorativi | `DATA_PROJECT!L94/8` |
| Giorni del mese (modalità %) | % × giorni lavorativi del mese | `Allocazione %!N4`, `AB15` |
| Ricavo | giorni × prezzo/giorno del profilo | `DATA_PROJECT!D97 = fee × ore / 8` |
| Costo | giorni × costo/giorno del profilo | `DATA_PROJECT!D98 = costo/ora × ore` |
| FTE del mese | giorni del mese ÷ giorni lavorativi (= somma delle %) | `Allocazione %!N3` |
| FTE della riga (modalità %) | media delle % pesata sui giorni lavorativi dei mesi valorizzati | `Allocazione %!AA15` |

## Riepiloghi
| Grandezza | Formula | Foglio |
|---|---|---|
| Servizi Interni | righe con profili non esterni | `DATA_PROJECT!D6:E6` |
| Servizi Esterni | righe con il profilo **Esterni** (indicatore "esterno") | `DATA_PROJECT!D7:E7` |
| Contingency di fase | ricavi della fase × % della fase; **nessun costo** | `DATA_PROJECT!M20…`, `E9` |
| Margine | ricavi − costi | `F6` |
| Margine % | margine ÷ ricavi | `DASHBOARD!F7` |
| C/R | costi ÷ ricavi | `DASHBOARD!H7` |
| Quota ore per profilo | ore del profilo ÷ ore totali | `DATA_PROJECT!D95` |

## KPI della dashboard
| KPI | Formula | Foglio |
|---|---|---|
| Prezzo progetto | ricavi interni + esterni + contingency | `DASHBOARD!C3` |
| Max sconto | **valore inserito da chi compila** (0-100%) | `DASHBOARD!I3` (cella manuale) |
| Prezzo vendita min | prezzo progetto × (1 − max sconto) | `DASHBOARD!D3` |
| GG totali | giornate base (senza contingency), esterni inclusi | `DASHBOARD!F3` |
| GG Project Management | giornate delle righe con il flag PM | `DASHBOARD!H3` |
| GG attività tecniche | GG totali − GG PM | `DASHBOARD!G3` |
| Fee media min | prezzo vendita min ÷ GG totali | `DASHBOARD!E3` |
| Fee media firmata | prezzo firmato ÷ GG totali | `DASHBOARD!E4` |
| Margine firmato | prezzo firmato − costi | `DASHBOARD!F12` |
| Margine % firmato | margine firmato ÷ prezzo firmato | `DASHBOARD!E12` |
| C/R firmato | costi ÷ prezzo firmato | `DASHBOARD!G12` |
| Giornate / settimane con contingency | giornate di fase × (1 + %) | `DATA_PROJECT!M8`, `M9` |

Con prezzo firmato pari a zero il foglio mostra margine negativo e percentuali 0%; il motore restituisce il margine negativo e percentuali non disponibili.

## Differenze volute rispetto al foglio
1. **Contingency fase per fase.** Il foglio calcola una media pesata sulle ore e la applica al ricavo totale (`DATA_PROJECT!M6`, `M16`). Il motore applica a ogni fase la sua percentuale ai ricavi della fase. Se tutte le fasi hanno la stessa percentuale i risultati coincidono; se differiscono, il foglio sottostima. Nello scenario di prova (PM 20%, SD 5%, TA 10%): motore 4.222,50 contro foglio 3.910,05 (−312,45).
2. **Prezzo firmato mancante**: "n/d" invece di 0%.

## Validazione
I test (`backend/tests/test_engine_*.py`) confrontano il motore con il foglio:

- **CE reale** (468 ore, 9 fasi): ricavi 47.162,50, costi 20.200,00, margine 26.962,50 (57,17%), 58,5 giornate (48,5 tecniche + 10 PM), fee media 806,20, ripartizione per profilo.
- **Scenario A** (ricalcolato con LibreOffice): contingency 10%, max sconto 10%, prezzo firmato 40.000 → prezzo 51.878,75, prezzo min 46.690,88, fee media 798,13 / 683,76, margine firmato 19.800,00 (49,5%).
- **Scenario B** (ricalcolato con LibreOffice): griglia % su 4 mesi con 5 giorni non lavorativi a gennaio → 148,85 giornate, ricavi 125.762,50, costi 56.714,00, e i valori di ogni mese e di ogni riga.
- Regole e casi limite calcolati a mano, 17 casi di dati non validi, invarianti su 300 CE casuali (le giornate tornano sempre esatte).
- Controllo di sensibilità: introducendo di proposito 8 errori di calcolo nel motore, i test li individuano tutti.

Le colonne FTE del foglio usano funzioni solo-Google e LibreOffice non le calcola: quei valori sono verificati con calcoli a mano.

## Come si usa
```python
from datetime import date
from decimal import Decimal as D
from app.engine import CEInput, LineInput, PhaseInput, ProfileRate, calculate

ce = CEInput(
    start_date=date(2026, 1, 20), end_date=date(2026, 4, 20), mode="hours",
    phases=[PhaseInput("Analisi", [LineInput("Interviste", "Senior", hours=D("24"))], D("10"))],
    rates={"Senior": ProfileRate(D("850"), D("330"))},
    non_working_days={date(2026, 1, 1): 5},   # mese -> giorni non lavorativi
)
risultato = calculate(ce)          # CalculationError se i dati non sono validi
risultato.total.revenue, risultato.kpis.price_min, risultato.monthly
```
