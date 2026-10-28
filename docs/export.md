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
- **Costi vari** (solo se il CE ne ha): descrizione, costo e ricarico modificabili, totale di riga `=ROUND(costo×(1+ricarico),2)` e margine; il riepilogo ha una riga «Costi vari» che la richiama, e prezzo, sconto e fee media si ricalcolano di conseguenza (la fee media solo sui servizi).
- **Fasi**: totali e **contingency** per fase. **Profili**: ore, quota, ricavi e costi per profilo. **Tariffe**: le tariffe congelate nel CE.
- **Staffing mensile**: giorni feriali e non lavorativi del mese, giorni per riga e per mese, FTE, ricavi e costi mensili.

**Le celle blu su fondo giallo (o con testo blu) sono modificabili** e il file si ricalcola: ore, tariffe, percentuale di contingency, giorni non lavorativi, max sconto, prezzo firmato, allocazioni % (modalità percentuali). Cambiando il profilo di una riga, tariffe e classificazione interno/esterno si aggiornano da sole. Le formule usano solo funzioni di Excel 2007 (`SUM`, `SUMIF`, `SUMPRODUCT`, `VLOOKUP`, `IF`) e il file non contiene collegamenti ad altri file.

Limiti da conoscere:
- Nella modalità **ore** la ripartizione delle ore sui mesi è calcolata dal portale e **non si aggiorna** se modifichi le ore nel foglio Dettaglio (lo dice una nota nel foglio). In modalità percentuali lo staffing è tutto vivo.
- Il file è una fotografia: **il portale resta la fonte ufficiale** del CE.
- Ricavi e costi mensili escludono la contingency (ricavo aggiuntivo di fase, senza costi) e i **costi vari** (non hanno un mese).

## CSV
Una riga per ogni riga del CE (codice, versione, fase, attività, profilo, collaboratore, PM, esterno, ore, giorni, tariffe, ricavo, costo, margine, contingency di fase e, in coda, ricarico %); i costi vari sono righe con fase «Costi vari», senza ore né tariffe. Formato per **Excel italiano**: UTF-8 con BOM, separatore `;`, virgola decimale, date `gg/mm/aaaa`. I CSV riepilogativi e gli elenchi seguono lo stesso formato.

## PDF

Stile «moderno» del marchio (CL-036): **fascia nera** in alto con il logo bianco, il titolo, lo stato (Bozza, Approvato…) e un filo sfumato ciano-turchese; nelle pagine successive una fascia sottile con il riferimento al CE. Riquadri per gli indicatori (il prezzo in ciano), **ciambella** costi/margine e barre per profilo o per fase disegnate come grafica vettoriale (nessuna immagine: file piccoli e nitidi a ogni ingrandimento), tabelle con intestazioni turchesi e totali con tinta chiara. Piè di pagina su fondo chiaro con «Pagina x di y».

- **Completo** (A4 orizzontale, "Riservato - uso interno"): testata, indicatori (prezzo progetto, costi, margine con la percentuale, giornate, fee media minima; sotto C/R, giornate di management e di delivery, prezzo minimo), ciambella e barre, ricavi e costi (con la riga «Costi vari»), **divisione per business unit**, dettaglio per fase con subtotali e contingency, **sezione «Costi vari»** con le righe, riepilogo per profilo, staffing mensile, numero di pagina e data di generazione. Se il margine non è calcolabile la ciambella dice «n/d»; se è negativo è rossa e lo dice; oltre il 100% l'anello non esce dal cerchio.
- **Divisione per business unit** (solo nel PDF completo, perché ha costi e margini): una riga per business unit con giornate, ricavi, costi, margine, margine % e quota dei ricavi del CE. Ogni riga del CE è attribuita alla business unit del collaboratore indicato (quella della sua practice **attuale**); le righe **senza collaboratore**, la **contingency** (ricavo senza costi) e i **costi vari** (senza giornate) hanno una riga a parte, così le righe sommano sempre al totale del CE. Non compare se il CE non ha righe né nel riepilogo.
- **Esito**: se il CE ha un esito, la testata dei PDF (completo, riepilogo e viewer) dice «Esito: Close Won» o «Close Lost» (nel completo anche la data); la nota non compare mai nel riepilogo.
- **Riepilogo** (A4 verticale): giornate totali e ricavi totali nei riquadri, barre dei ricavi per fase, giornate di management e delivery, ricavi per fase, totale generale. Niente ciambella: non mostra costi né margini. Se la versione non è approvata lo dice. Se il CE ha righe con collaboratori, c'è anche la tabella **«Ricavi per business unit»**: **solo euro e quota dei ricavi** (mai giornate, costi o margini). Ogni riga è attribuita alla business unit del collaboratore indicato (quella della sua practice attuale); le righe senza collaboratore e i **costi vari** (solo il ricavo) sono a parte e la **contingency non compare a parte**: si ripartisce tra le business unit in proporzione ai ricavi delle loro righe (a centesimi, con il resto sulla più grande), così le righe sommano al totale e il riepilogo non rivela quanto vale. Vale per il PDF riepilogativo di chi modifica, del viewer (CE approvati) e delle integrazioni; Excel e CSV del riepilogo non cambiano.
- **Testi lunghi**: nella fascia il titolo si accorcia con «...» (il codice e il nome completi restano nelle informazioni e nel piè di pagina); nei riquadri un importo molto grande si rimpicciolisce invece di uscire. Le tabelle lunghe si spezzano ripetendo l'intestazione.
- **Logo**: `backend/app/assets/logo.png` (nero) e `logo-white.png` (bianco, per la fascia nera). Un logo personalizzato senza la sua versione bianca accanto si appoggia su una piastra chiara; se manca del tutto compare il nome del portale in testo.
- **Font**: **DM Sans** (Light, Regular, Medium, Bold), incorporato, in `backend/app/assets/fonts/` con il testo della licenza **SIL Open Font License 1.1** (`OFL.txt`), che va distribuita con i file. Se i file dei font mancassero si ripiega su Helvetica e il PDF si produce comunque. I caratteri che i font non hanno compaiono come `?` invece di rompere il file.
- **Verifica visiva**: i test controllano il contenuto; l'aspetto si guarda generando un PDF e trasformandolo in immagine (`pdftoppm -png -r 80 file.pdf pagina`).

## Cosa esce per il viewer
Solo: codice, cliente, progetto, date, versione, data di approvazione, giornate di management e di delivery, ricavi per fase (contingency inclusa), **una sola voce «Costi vari» con il ricavo** (mai descrizioni, costo o ricarico) e totale. Mai costi, margini, ore, righe, attività, profili, collaboratori, tariffe, note, opportunità Salesforce o business unit. In Excel è **un solo foglio, solo valori**, senza fogli nascosti, commenti o collegamenti.

## Sicurezza
- **Formule**: un testo che inizia con `=`, `+`, `-` o `@` (per esempio il nome di un'attività) non può essere eseguito aprendo il file: in CSV viene preceduto da `'`, in Excel resta una cella di testo.
- **Riservatezza**: i test controllano i file per intero (celle, nomi dei fogli, proprietà, ogni parte interna dello zip di Excel, testo e metadati del PDF, intero CSV) cercando costi, margini, tariffe, attività, collaboratori e note. Includono una prova di sensibilità: lo stesso controllo, sui file completi, trova i dati.
- **Tracciabilità**: ogni esportazione è nello storico (`GET /ce/{id}/history`, e per elenchi e dashboard nel registro delle modifiche).

## Come sono collaudati
L'Excel viene **ricalcolato da LibreOffice** e confrontato con il motore sul CE reale (47.162,50 / 20.200,00 / 58,5 giornate) e sugli scenari del foglio: contingency, sconto, prezzo firmato e griglia a percentuali. Un test modifica i dati nel file e verifica che i totali cambino. I PDF vengono letti con una libreria PDF; la vista ridotta è provata su ogni formato. I test di Excel con ricalcolo richiedono LibreOffice e vengono saltati dove non è installato.
