#!/usr/bin/env bash
# Controllo di fumo del portale: risponde? serve il frontend? le protezioni sono attive?
#
#   infra/scripts/smoke.sh https://indirizzo-del-portale [--prod]
#
# Con --prod controlla anche che l'accesso simulato non esista e che ci sia HSTS (richiede https).
set -euo pipefail

BASE="${1:?Uso: smoke.sh URL [--prod]}"
BASE="${BASE%/}"
PROD=false
[ "${2:-}" = "--prod" ] && PROD=true

fail() { echo "ERRORE: $*" >&2; exit 1; }
ok() { echo "ok  $*"; }

# 1. il servizio si avvia (può servire un minuto: avvio a freddo)
for i in $(seq 1 30); do
  if curl -fsS -m 10 "$BASE/api/v1/health" -o /tmp/smoke-health.json 2>/dev/null; then break; fi
  [ "$i" = 30 ] && fail "il servizio non risponde su $BASE/api/v1/health"
  sleep 2
done
python3 -c "import json,sys; sys.exit(0 if json.load(open('/tmp/smoke-health.json')).get('status') == 'ok' else 1)" \
  || fail "/api/v1/health non risponde {\"status\": \"ok\"}"
ok "/api/v1/health"

# 2. il frontend
HOME_HTML="$(curl -fsS -m 10 "$BASE/")" || fail "la pagina iniziale non risponde"
echo "$HOME_HTML" | grep -q 'id="root"' || fail "la pagina iniziale non contiene l'applicazione (frontend non incluso?)"
ok "pagina iniziale con il frontend"
curl -fsS -m 10 "$BASE/ce/qualunque-cosa" | grep -q 'id="root"' || fail "le pagine dell'applicazione non tornano index.html"
ok "indirizzi dell'applicazione (/ce/...) gestiti dal frontend"

# 3. le risorse con l'impronta sono in cache a lungo
ASSET="$(echo "$HOME_HTML" | grep -o '/assets/[^"]*\.js' | head -1)"
[ -n "$ASSET" ] || fail "nessuno script in /assets nella pagina iniziale"
curl -fsSI -m 10 "$BASE$ASSET" | tr -d '\r' | grep -qi '^cache-control:.*immutable' || fail "$ASSET non è in cache a lungo"
ok "$ASSET in cache a lungo"

# 4. configurazione pubblica
curl -fsS -m 10 "$BASE/api/v1/config" -o /tmp/smoke-config.json || fail "/api/v1/config non risponde"
DEV="$(python3 -c "import json; print(json.load(open('/tmp/smoke-config.json'))['dev_login'])")"
if $PROD && [ "$DEV" != "False" ]; then fail "l'accesso simulato è attivo in produzione"; fi
ok "/api/v1/config (accesso simulato: $DEV)"

# 5. intestazioni di sicurezza
HEADERS="$(curl -fsSI -m 10 "$BASE/" | tr -d '\r')"
for h in content-security-policy x-frame-options x-content-type-options referrer-policy; do
  echo "$HEADERS" | grep -qi "^$h:" || fail "manca l'intestazione $h"
done
ok "intestazioni di sicurezza"
if $PROD; then
  case "$BASE" in https://*) echo "$HEADERS" | grep -qi '^strict-transport-security:' || fail "manca HSTS" ; ok "HSTS" ;; esac
  DOCS="$(curl -sS -m 10 "$BASE/api/v1/openapi.json" -o /dev/null -w '%{http_code}')"
  [ "$DOCS" = 404 ] || fail "la documentazione dell'API è pubblica in produzione ($DOCS)"
  ok "documentazione dell'API non pubblicata"
fi

# 6. l'API è protetta e gli indirizzi sbagliati non danno HTML
CODE="$(curl -sS -m 10 "$BASE/api/v1/ce" -o /dev/null -w '%{http_code}')"
[ "$CODE" = 401 ] || fail "/api/v1/ce senza accesso deve rispondere 401 (risponde $CODE)"
ok "l'API chiede l'accesso"
curl -sS -m 10 "$BASE/api/v1/non-esiste" | grep -q '"detail"' || fail "un indirizzo API sbagliato non risponde in JSON"
ok "indirizzi API sbagliati in JSON"

echo "Tutti i controlli superati su $BASE"
