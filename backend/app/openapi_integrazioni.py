# ruff: noqa: E501
"""Documentazione OpenAPI delle sole API esposte ai programmi esterni (`/api/v1/integrazioni`).

Si ricava dallo schema completo del portale: stesse rotte, stessi modelli, nessuna copia scritta a mano.
Produce il file `docs/api-integrazioni/openapi.json` e la pagina Swagger `docs/api-integrazioni/index.html`
(con lo schema incorporato, apribile da sola). `make api-integrazioni` li rigenera; un test verifica che
siano allineati al codice.
"""

import copy
import json
from typing import Any

from fastapi import FastAPI

PREFIX = "/api/v1/integrazioni"
# campi interni che le integrazioni non possono inviare: non compaiono nella documentazione esterna
INTERNAL_FIELDS = {"ContentIn": ("extra_costs", "discounts")}
SWAGGER_UI_VERSION = "5.17.14"

DESCRIPTION = """\
API per i programmi esterni che leggono o creano Conti Economici (CE) nel portale.

## Autenticazione
Ogni richiesta porta l'**ID token Google dell'account di servizio** dell'integrazione, con **audience uguale
all'indirizzo del portale**, nell'intestazione `Authorization: Bearer <token>`. Il portale ne controlla firma,
scadenza, issuer e audience e cerca l'email dell'account in un elenco gestito dagli amministratori.

## Permessi
Ogni integrazione ha solo i permessi che le sono stati dati: `read`, `create`, `edit`, `export`. Senza il
permesso richiesto la risposta è `403`; la disattivazione ha effetto dalla richiesta successiva.

## Limiti
Al massimo **una richiesta al secondo** per integrazione: oltre, `429` con l'intestazione `Retry-After`.

## Che cosa non si vede e non si scrive
Costi, margini, costi vari e sconti sono dati interni: le integrazioni non li ricevono (nei riepiloghi) e non
possono inviarli (`422`). Un'integrazione modifica solo le bozze create da lei.
"""


def _refs(node: Any, found: set[str]) -> None:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            found.add(ref.rsplit("/", 1)[1])
        for value in node.values():
            _refs(value, found)
    elif isinstance(node, list):
        for value in node:
            _refs(value, found)


def build(app: FastAPI) -> dict[str, Any]:
    """Schema OpenAPI con le sole rotte `/integrazioni`, i modelli che usano e il loro schema di sicurezza."""
    full = app.openapi()
    paths = {p: v for p, v in full["paths"].items() if p.startswith(PREFIX)}
    schemas = copy.deepcopy(full.get("components", {}).get("schemas", {}))
    for model, fields in INTERNAL_FIELDS.items():
        for field in fields:
            schemas[model].get("properties", {}).pop(field, None)
    needed: set[str] = set()
    _refs(paths, needed)
    pending = list(needed)
    while pending:  # modelli che richiamano altri modelli
        nested: set[str] = set()
        _refs(schemas[pending.pop()], nested)
        pending += [n for n in nested if n not in needed]
        needed |= nested
    used = {
        name
        for item in paths.values()
        for op in item.values()
        for sec in op.get("security", [])
        for name in sec
    }
    schemes = {
        k: v for k, v in full.get("components", {}).get("securitySchemes", {}).items() if k in used
    }
    return {
        "openapi": full["openapi"],
        "info": {
            "title": "Portale Conti Economici: API per le integrazioni",
            "version": full["info"]["version"],
            "description": DESCRIPTION,
        },
        "servers": [
            {
                "url": "https://INDIRIZZO-DEL-PORTALE",
                "description": "Sostituisci con l'indirizzo del portale",
            }
        ],
        "paths": paths,
        "components": {
            "schemas": {k: schemas[k] for k in sorted(needed)},
            **({"securitySchemes": schemes} if schemes else {}),
        },
    }


def spec_json(app: FastAPI) -> str:
    return json.dumps(build(app), indent=1, ensure_ascii=False) + "\n"


def swagger_html(spec: str) -> str:
    """Pagina Swagger UI con lo schema incorporato (la libreria arriva da un CDN, a versione fissa)."""
    inline = spec.replace("</", "<\\/")  # lo schema sta in un tag <script>
    return f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>API per le integrazioni - Portale Conti Economici</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@{SWAGGER_UI_VERSION}/swagger-ui.css">
<style>body{{margin:0}}</style>
</head>
<body>
<div id="swagger-ui"></div>
<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@{SWAGGER_UI_VERSION}/swagger-ui-bundle.js"></script>
<script>
window.ui = SwaggerUIBundle({{
  spec: {inline.strip()},
  dom_id: "#swagger-ui",
  deepLinking: true,
  docExpansion: "list",
  tryItOutEnabled: false,
  supportedSubmitMethods: []
}});
</script>
</body>
</html>
"""


def write(app: FastAPI, directory: str) -> None:
    spec = spec_json(app)
    with open(f"{directory}/openapi.json", "w", encoding="utf-8") as fh:
        fh.write(spec)
    with open(f"{directory}/index.html", "w", encoding="utf-8") as fh:
        fh.write(swagger_html(spec))
