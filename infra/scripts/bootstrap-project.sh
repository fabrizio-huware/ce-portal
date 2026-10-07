#!/usr/bin/env bash
# Prepara un progetto Google Cloud per Terraform: abilita le API di base e crea il bucket dello stato.
# Si lancia una sola volta per progetto, con il proprio account (gcloud auth login).
#
#   infra/scripts/bootstrap-project.sh ID-DEL-PROGETTO [regione]
set -euo pipefail

PROJECT="${1:?Uso: bootstrap-project.sh ID-DEL-PROGETTO [regione]}"
REGION="${2:-europe-west8}"
BUCKET="${PROJECT}-tfstate"

command -v gcloud >/dev/null || { echo "gcloud non è installato: https://cloud.google.com/sdk/docs/install" >&2; exit 1; }

echo "Progetto: $PROJECT · regione: $REGION · bucket dello stato: gs://$BUCKET"
gcloud projects describe "$PROJECT" >/dev/null || { echo "Il progetto $PROJECT non esiste o non hai accesso." >&2; exit 1; }
BILLING="$(gcloud billing projects describe "$PROJECT" --format='value(billingEnabled)' 2>/dev/null || true)"
[ "$BILLING" = "True" ] || { echo "Il progetto non ha la fatturazione attiva: collegala nella console (Fatturazione) e rilancia." >&2; exit 1; }

# Le API che servono a Terraform stesso; tutte le altre le abilita Terraform.
gcloud services enable serviceusage.googleapis.com cloudresourcemanager.googleapis.com iam.googleapis.com storage.googleapis.com --project "$PROJECT"

if gcloud storage buckets describe "gs://$BUCKET" --project "$PROJECT" >/dev/null 2>&1; then
  echo "Il bucket gs://$BUCKET esiste già."
else
  gcloud storage buckets create "gs://$BUCKET" --project "$PROJECT" --location "$REGION" \
    --uniform-bucket-level-access --public-access-prevention
  gcloud storage buckets update "gs://$BUCKET" --versioning # conserva le versioni dello stato: si può tornare indietro
fi

cat <<MSG

Fatto. Prossimi passi (vedi docs/deploy.md):
  cd infra/terraform/envs/<test|prod>
  cp backend.hcl.example backend.hcl          # bucket: $BUCKET
  cp terraform.tfvars.example terraform.tfvars # inserisci i tuoi valori
  terraform init -backend-config=backend.hcl
  terraform plan
MSG
