#!/usr/bin/env bash
# Controlla le variabili usate dalla pubblicazione, MOSTRA i valori che il flusso riceve davvero (sono identificativi,
# non segreti) e dice dove andrà l'immagine.
#
# Due modi:
#  - senza CHECK_PREFIX (lavoro «build»): variabili TEST_* obbligatorie, PROD_* facoltative. Legge REGION,
#    TEST_PROJECT, TEST_WIP, TEST_SA, PROD_PROJECT, PROD_WIP, PROD_SA e scrive prod_enabled=true|false in $GITHUB_OUTPUT.
#  - con CHECK_PREFIX=TEST|PROD (lavoro di pubblicazione): controlla solo quell'ambiente. Legge REGION, PROJECT, WIP, SA.
#
# GitHub non accetta variabili vuote: per la produzione NON creare le variabili. Se sono state create con un
# segnaposto («-», «n/a», «none»…) vengono trattate come non impostate.
set -euo pipefail

fail() { echo "::error::$*" >&2; exit 1; }

# segnaposto che significano «non impostata»
unset_value() {
  local v="${1//[[:space:]]/}"
  case "${v,,}" in "" | "-" | "--" | "n/a" | "na" | "none" | "null" | "nessuna") return 0 ;; *) return 1 ;; esac
}

show() { echo "  $1 = «$2» (${#2} caratteri)"; }

check_wip() {
  local name="$1" value="$2" label="$3"
  if [[ "$value" =~ [[:space:]] ]]; then
    fail "$name contiene spazi o a-capo (valore: «$value»): reincollalo senza spazi prima o dopo."
  fi
  if [[ ! "$value" =~ ^projects/[0-9]+/locations/global/workloadIdentityPools/[A-Za-z0-9._-]+/providers/[A-Za-z0-9._-]+$ ]]; then
    fail "$name vale «$value», ma deve essere il nome completo del fornitore di identità, nella forma projects/NUMERO/locations/global/workloadIdentityPools/…/providers/github (senza «//iam.googleapis.com/» davanti). Si ottiene con: terraform output -raw workload_identity_provider (dalla cartella infra/terraform/envs/$label). Se nella schermata di GitHub il valore sembra giusto, la variabile esiste forse due volte (Repository, Environment o organizzazione) con valori diversi: il flusso usa quella dell'Environment se c'è, altrimenti quella del repository."
  fi
}

check_env() { # prefisso progetto fornitore account etichetta
  local prefix="$1" project="$2" wip="$3" sa="$4" label="$5"
  echo "Variabili ${prefix}_* ricevute dal flusso:"
  show "${prefix}_GCP_PROJECT" "$project"
  show "${prefix}_WORKLOAD_IDENTITY_PROVIDER" "$wip"
  show "${prefix}_DEPLOY_SERVICE_ACCOUNT" "$sa"
  check_wip "${prefix}_WORKLOAD_IDENTITY_PROVIDER" "$wip" "$label"
  case "$sa" in
    *"@$project.iam.gserviceaccount.com") ;;
    *) fail "${prefix}_DEPLOY_SERVICE_ACCOUNT («$sa») non appartiene al progetto indicato in ${prefix}_GCP_PROJECT («$project»): uno dei due valori è sbagliato. Copiali dall'output di «terraform output github_variables» dell'ambiente $label." ;;
  esac
}

REGION="${REGION:-}"

# ------------------------------------------------------------ un solo ambiente (lavoro di pubblicazione)
if [ -n "${CHECK_PREFIX:-}" ]; then
  label="$(echo "$CHECK_PREFIX" | tr '[:upper:]' '[:lower:]')"
  missing=""
  for v in REGION PROJECT WIP SA; do unset_value "${!v:-}" && missing="$missing $v"; done
  [ -z "$missing" ] || fail "Parametri mancanti per l'ambiente $label:$missing. Variabili del repository (o dell'Environment) richieste: GCP_REGION, ${CHECK_PREFIX}_GCP_PROJECT, ${CHECK_PREFIX}_WORKLOAD_IDENTITY_PROVIDER, ${CHECK_PREFIX}_DEPLOY_SERVICE_ACCOUNT."
  # shellcheck disable=SC2153 # PROJECT, WIP e SA arrivano dall'ambiente: li imposta il flusso
  check_env "$CHECK_PREFIX" "$PROJECT" "$WIP" "$SA" "$label"
  echo "Ambiente $label: progetto $PROJECT, registro $REGION-docker.pkg.dev/$PROJECT/ce-portal"
  exit 0
fi

# ------------------------------------------------------------ lavoro «build»: test obbligatorio, produzione facoltativa
missing=""
for v in REGION TEST_PROJECT TEST_WIP TEST_SA; do
  unset_value "${!v:-}" && missing="$missing $v"
done
if [ -n "$missing" ]; then
  fail "Variabili mancanti per l'ambiente di test:$missing (un valore «-» conta come mancante). Nomi esatti: GCP_REGION, TEST_GCP_PROJECT, TEST_WORKLOAD_IDENTITY_PROVIDER, TEST_DEPLOY_SERVICE_ACCOUNT. Devono essere variabili (non Secrets) del repository o dell'Environment «test». Terraform stampa nomi e valori giusti con: terraform output github_variables"
fi
check_env TEST "$TEST_PROJECT" "$TEST_WIP" "$TEST_SA" test

prod_set=0
for v in PROD_PROJECT PROD_WIP PROD_SA; do
  unset_value "${!v:-}" || prod_set=$((prod_set + 1))
done
case "$prod_set" in
  0) PROD=false ;;
  3) PROD=true ;;
  *) fail "Le variabili di produzione (PROD_GCP_PROJECT, PROD_WORKLOAD_IDENTITY_PROVIDER, PROD_DEPLOY_SERVICE_ACCOUNT) vanno impostate tutte e tre oppure nessuna: ne risultano impostate $prod_set su 3. Se non hai ancora la produzione NON creare queste variabili (GitHub non ammette valori vuoti) ed eliminale se esistono." ;;
esac
if [ "$PROD" = true ]; then
  check_env PROD "$PROD_PROJECT" "$PROD_WIP" "$PROD_SA" prod
  [ "$PROD_PROJECT" != "$TEST_PROJECT" ] || echo "::warning::Test e produzione usano lo stesso progetto ($TEST_PROJECT): non c'è separazione tra gli ambienti."
fi

echo "Test:       progetto $TEST_PROJECT  →  registro $REGION-docker.pkg.dev/$TEST_PROJECT/ce-portal"
if [ "$PROD" = true ]; then
  echo "Produzione: progetto $PROD_PROJECT  →  registro $REGION-docker.pkg.dev/$PROD_PROJECT/ce-portal"
else
  echo "::notice::Produzione non configurata: si pubblica solo su test."
fi
[ -z "${GITHUB_OUTPUT:-}" ] || echo "prod_enabled=$PROD" >> "$GITHUB_OUTPUT"
