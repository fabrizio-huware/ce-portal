# Dati di prova del motore di calcolo

`ce_bonga.json` è estratto dal foglio reale **PS-BONGA-AI-PJT - CE di progetto**:

- `phases`, `rates`, `expected`: struttura e risultati del CE originale (cache del foglio).
- `scenarios`: tre varianti del foglio **ricalcolate da LibreOffice** dopo aver cambiato alcuni input
  (contingency, sconto, prezzo firmato, griglia % di allocazione). Servono da riferimento
  indipendente: il motore deve ottenere gli stessi numeri del foglio.

Le colonne FTE del foglio usano funzioni solo-Google e non sono ricalcolabili da LibreOffice:
quei valori nei test sono verificati con calcoli a mano.
