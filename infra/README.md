# Infrastruttura (Step 9)

Questa cartella conterrà il codice Terraform e i Dockerfile per il deploy su Google Cloud.

Architettura prevista, per ciascun ambiente (`test` e `prod`, in progetti GCP separati):

- Cloud Run: servizio API (FastAPI) e servizio frontend (React)
- Cloud SQL for PostgreSQL
- Secret Manager (credenziali Mailjet, parametri OAuth, password DB)
- Artifact Registry (immagini container)
- Workload Identity Federation per i deploy da GitHub Actions (nessuna chiave di service account nel repository)

Regione: `europe-west8` (Milano), salvo diversa decisione.
