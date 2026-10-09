#!/usr/bin/env bash
# Controlla le variabili del repository GitHub usate dalla pubblicazione e dice chiaramente dove andrà l'immagine.
# Lette dall'ambiente: REGION, TEST_PROJECT, TEST_WIP, TEST_SA, PROD_PROJECT, PROD_WIP, PROD_SA.
# Scrive in $GITHUB_OUTPUT (se esiste): prod_enabled=true|false.
#
# La produzione è facoltativa: se le tre variabili PROD_* sono tutte vuote si pubblica solo su test.
set -euo pipefail

fail() { echo "::error::$*" >&2; exit 1; }

missing=""
for v in REGION TEST_PROJECT TEST_WIP TEST_SA; do
  [ -n "${!v:-}" ] || missing="$missing $v"
done
if [ -n "$missing" ]; then
  fail "Variabili del repository mancanti per l'ambiente di test:$missing. Vedi docs/deploy.md, passo «Configura GitHub» (nomi: GCP_REGION, TEST_GCP_PROJECT, TEST_WORKLOAD_IDENTITY_PROVIDER, TEST_DEPLOY_SERVICE_ACCOUNT)."
fi

prod_set=0
for v in PROD_PROJECT PROD_WIP PROD_SA; do
  [ -z "${!v:-}" ] || prod_set=$((prod_set + 1))
done
case "$prod_set" in
  0) PROD=false ;;
  3) PROD=true ;;
  *) fail "Le variabili di produzione (PROD_GCP_PROJECT, PROD_WORKLOAD_IDENTITY_PROVIDER, PROD_DEPLOY_SERVICE_ACCOUNT) vanno impostate tutte e tre oppure nessuna: ne risultano impostate $prod_set su 3." ;;
esac

# Il progetto indicato deve comparire nel nome del fornitore di identità (projects/NUMERO/...): non lo si può
# confrontare (c'è il numero, non l'ID), ma l'account di servizio contiene l'ID del progetto: controlliamo quello.
case "$TEST_SA" in
  *"@$TEST_PROJECT.iam.gserviceaccount.com") ;;
  *) fail "TEST_DEPLOY_SERVICE_ACCOUNT ($TEST_SA) non appartiene al progetto indicato in TEST_GCP_PROJECT ($TEST_PROJECT): uno dei due valori è sbagliato. Copiali dall'output di «terraform output» dell'ambiente di test." ;;
esac
if [ "$PROD" = true ]; then
  case "$PROD_SA" in
    *"@$PROD_PROJECT.iam.gserviceaccount.com") ;;
    *) fail "PROD_DEPLOY_SERVICE_ACCOUNT ($PROD_SA) non appartiene al progetto indicato in PROD_GCP_PROJECT ($PROD_PROJECT)." ;;
  esac
  [ "$PROD_PROJECT" != "$TEST_PROJECT" ] || echo "::warning::Test e produzione usano lo stesso progetto ($TEST_PROJECT): i nomi delle risorse sono diversi, ma non c'è separazione tra gli ambienti."
fi

echo "Test:       progetto $TEST_PROJECT  →  registro $REGION-docker.pkg.dev/$TEST_PROJECT/ce-portal"
if [ "$PROD" = true ]; then
  echo "Produzione: progetto $PROD_PROJECT  →  registro $REGION-docker.pkg.dev/$PROD_PROJECT/ce-portal"
else
  echo "::notice::Produzione non configurata (variabili PROD_* vuote): si pubblica solo su test."
fi
[ -z "${GITHUB_OUTPUT:-}" ] || echo "prod_enabled=$PROD" >> "$GITHUB_OUTPUT"
