# Convenzioni di sviluppo

## Branch e release
- `main` è sempre rilasciabile e protetto: si modifica solo tramite Pull Request con CI verde.
- Branch di lavoro: `feature/<descrizione>`, `fix/<descrizione>`.
- Un push su `main` rilascia automaticamente sull'ambiente **test**; il rilascio in **prod** richiede approvazione manuale (Step 9).

## Commit
Formato [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.

## Qualità del codice
- Backend: `ruff` (lint e format), `pytest`. Ogni funzione di calcolo ha test con valori numerici verificati.
- Frontend: TypeScript strict, `npm run lint` e `npm run build` devono passare.
- Le modifiche al database passano sempre da una migrazione Alembic, mai da modifiche manuali.

## Sicurezza
- Nessun segreto nel repository: in locale si usa `backend/.env` (ignorato da git), in cloud Secret Manager.
- I permessi per ruolo si applicano **sempre lato backend**; il frontend nasconde le funzioni solo per usabilità.
- Il viewer non deve mai ricevere dalle API costi, margini o righe di dettaglio.

## Lingua
Interfaccia e documentazione in italiano. Codice, nomi di variabili e commenti tecnici in inglese.
