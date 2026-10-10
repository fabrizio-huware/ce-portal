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
- Ogni nuovo endpoint va aggiunto alla matrice in `backend/tests/test_permissions_matrix.py` con i ruoli ammessi: il test fallisce se manca.
- Le scritture registrano sempre una riga nell'audit log (`app/services/audit.py`).
- Non cancellare anagrafiche: si disattivano.
- Ogni nuovo export: testo utente sempre neutralizzato (`neutralize` / `put`), nome file con `safe_filename`, registrazione nello storico, e un test di riservatezza se può raggiungere il viewer. Le viste ridotte nascono da schemi dedicati, mai da filtri su quelle complete.
- Nelle email **mai costi o margini**, solo il prezzo. Ogni nuova notifica va preparata con `app/notifications` nella stessa transazione dell'evento, con una chiave anti-doppione, e ha test sui destinatari (mai viewer, mai chi compie l'azione, mai utenti disattivati).
- Calcoli economici solo in `app/engine`, con `Decimal` (mai `float`) e senza accesso al database. Ogni modifica alle formule va confrontata con il foglio di riferimento e documentata in `docs/formule.md`.

## Lingua
Interfaccia e documentazione in italiano. Codice, nomi di variabili e commenti tecnici in inglese.

- Dopo ogni modifica alle API del backend esegui `make api-types` e fai commit di `frontend/openapi.json` e `frontend/src/api/schema.d.ts`: la CI li controlla.
- **Test di Terraform** (`infra/terraform/modules/ce_portal/tests`): le asserzioni devono confrontare solo valori che dipendono dalle variabili in ingresso o da attributi scritti nella configurazione. Gli attributi "calcolati" (nomi, email e identificativi creati da Google dopo l'apply) i provider simulati li forniscono in modo diverso in Terraform e in OpenTofu: un test che passa con uno può fallire con l'altro. La CI usa Terraform.
- Se cambi le dipendenze in `backend/pyproject.toml`, o vuoi aggiornarle, lancia `make lock` **e poi `make api-types`**, e fai commit di `backend/requirements.lock`, `backend/requirements-dev.lock` e dello schema dell'API. L'immagine, la CI e chi sviluppa usano le stesse versioni esatte: una libreria che esce nuova non cambia nulla finché non la aggiorni tu (la CI confronta lo schema dell'API con quello versionato, e una versione diversa lo cambierebbe).
- Le cose che i test creano e non si possono eliminare (utenti, clienti, collaboratori, profili) vanno **disattivate** a fine test; i CE di prova hanno codice `PS-E2E…` e si ripuliscono da soli.
- Ogni nuova schermata ha test nel browser per desktop e smartphone e passa il controllo di accessibilità (`frontend/e2e/a11y.spec.ts`).
