# Export: Excel, CSV, PDF

Tutti gli export escono con `Content-Disposition: attachment`, `Cache-Control: no-store` e `X-Content-Type-Options: nosniff`. Nomi dei file sicuri e in ASCII (`PS-BONGA-AI-PJT_v1.xlsx`). **Ogni esportazione è registrata nello storico** (chi, quando, formato, variante, versione), anche quella del viewer. Gli orari nei file sono in **ora italiana**.

## Endpoint

| Operazione | Percorso | Chi |
|---|---|---|
| Esporta un CE | `GET /ce/{id}/export?format=xlsx\|csv\|pdf&variant=full\|summary&version=n` | admin, presale |
| Esporta il riepilogo di un CE approvato | `GET /ce/summaries/{id}/export?format=pdf\|xlsx\|csv` | tutti |
| Esporta i risultati di una ricerca | `GET /ce/export?format=xlsx\|csv` + filtri della ricerca | admin, presale |
| Esporta l'elenco ridotto | `GET /ce/summaries/export?format=xlsx\|csv` | tutti |

- `variant=full` (default): completo, per uso interno. `variant=summary`: **lo stesso contenuto che vede il viewer**, utile agli editor per condividere un CE senza esporre costi.
- `version`: numero di versione; senza, l'ultima. Per il viewer si esporta sempre l'ultima versione **approvata**.
- Gli elenchi accettano gli stessi filtri della ricerca (cliente, progetto, codice, date, stato, autore) e al massimo **5000 righe**: oltre, risposta `422` con l'invito a restringere i filtri.
- `422` per formato o variante non validi (il PDF non è disponibile per gli elenchi); `404` per CE inesistente, eliminato o, per il viewer, non approvato.

## Excel completo (con formule vere)

Fogli: **Riepilogo**, **Dettaglio**, **Fasi**, **Profili**, **Staffing mensile**, **Tariffe**, **Note**.

- **Riepilogo**: testata, ricavi e costi per Servizi interni / esterni / Contingency / Totale, e gli indicatori della dashboard (prezzo progetto, max sconto, prezzo minimo, giornate, PM e delivery, settimane, fee media, prezzo firmato e margine firmato).
- **Dettaglio**: una riga per ogni riga del CE, divise per fase, con ore, giorni, tariffe, ricavo, costo, margine e subtotale di fase.
- **Fasi**: totali e **contingency** per fase. **Profili**: ore, quota, ricavi e costi per profilo. **Tariffe**: le tariffe congelate nel CE.
- **Staffing mensile**: giorni feriali e non lavorativi del mese, giorni per riga e per mese, FTE, ricavi e costi mensili.

**Le celle blu su fondo giallo (o con testo blu) sono modificabili** e il file si ricalcola: ore, tariffe, percentuale di contingency, giorni non lavorativi, max sconto, prezzo firmato, allocazioni % (modalità percentuali). Cambiando il profilo di una riga, tariffe e classificazione interno/esterno si aggiornano da sole. Le formule usano solo funzioni di Excel 2007 (`SUM`, `SUMIF`, `SUMPRODUCT`, `VLOOKUP`, `IF`) e il file non contiene collegamenti ad altri file.

Limiti da conoscere:
- Nella modalità **ore** la ripartizione delle ore sui mesi è calcolata dal portale e **non si aggiorna** se modifichi le ore nel foglio Dettaglio (lo dice una nota nel foglio). In modalità percentuali lo staffing è tutto vivo.
- Il file è una fotografia: **il portale resta la fonte ufficiale** del CE.
- Ricavi e costi mensili escludono la contingency (ricavo aggiuntivo di fase, senza costi).

## CSV
Una riga per ogni riga del CE (codice, versione, fase, attività, profilo, collaboratore, PM, esterno, ore, giorni, tariffe, ricavo, costo, margine, contingency di fase). Formato per **Excel italiano**: UTF-8 con BOM, separatore `;`, virgola decimale, date `gg/mm/aaaa`. I CSV riepilogativi e gli elenchi seguono lo stesso formato.

## PDF
- **Completo** (A4 orizzontale, "Riservato - uso interno"): intestazione, testata, indicatori, ricavi e costi, dettaglio per fase con subtotali e contingency, riepilogo per profilo, staffing mensile, numero di pagina e data di generazione.
- **Riepilogo** (A4 verticale): giornate di management e delivery, ricavi per fase, totale generale. Se la versione non è approvata lo dice.
- **Logo**: se esiste `backend/app/assets/logo.png` compare nell'intestazione, altrimenti il nome del portale in testo. Font standard (Helvetica): i caratteri non supportati compaiono come `?` invece di rompere il file. Il font definitivo del brand si decide con la grafica (Step 8).

## Cosa esce per il viewer
Solo: codice, cliente, progetto, date, versione, data di approvazione, giornate di management e di delivery, ricavi per fase (contingency inclusa) e totale. Mai costi, margini, ore, righe, attività, profili, collaboratori, tariffe, note, opportunità Salesforce o business unit. In Excel è **un solo foglio, solo valori**, senza fogli nascosti, commenti o collegamenti.

## Sicurezza
- **Formule**: un testo che inizia con `=`, `+`, `-` o `@` (per esempio il nome di un'attività) non può essere eseguito aprendo il file: in CSV viene preceduto da `'`, in Excel resta una cella di testo.
- **Riservatezza**: i test controllano i file per intero (celle, nomi dei fogli, proprietà, ogni parte interna dello zip di Excel, testo e metadati del PDF, intero CSV) cercando costi, margini, tariffe, attività, collaboratori e note. Includono una prova di sensibilità: lo stesso controllo, sui file completi, trova i dati.
- **Tracciabilità**: ogni esportazione è nello storico (`GET /ce/{id}/history`, e per elenchi e dashboard nel registro delle modifiche).

## Come sono collaudati
L'Excel viene **ricalcolato da LibreOffice** e confrontato con il motore sul CE reale (47.162,50 / 20.200,00 / 58,5 giornate) e sugli scenari del foglio: contingency, sconto, prezzo firmato e griglia a percentuali. Un test modifica i dati nel file e verifica che i totali cambino. I PDF vengono letti con una libreria PDF; la vista ridotta è provata su ogni formato. I test di Excel con ricalcolo richiedono LibreOffice e vengono saltati dove non è installato.
