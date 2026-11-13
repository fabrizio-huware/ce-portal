#!/usr/bin/env python3
"""Genera `api-swagger.html`: la documentazione Swagger delle API in un solo file, apribile senza server né rete.

In produzione `/docs` è spento di proposito. Questo file è una copia di SOLA LETTURA dello schema
(`frontend/openapi.json`, tenuto allineato al codice dal controllo `make api-types` della CI): le chiamate di prova
si fanno in locale (`make backend`, poi `/docs`), perché dal file il browser le bloccherebbe (il portale accetta
solo la propria origine). Serve `npm`, solo per scaricare `swagger-ui-dist`; il resto è libreria standard.

    python3 backend/scripts/build_swagger_html.py [--out api-swagger.html]
"""

import argparse
import copy
import json
import subprocess
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "frontend" / "openapi.json"

ACCESS_NOTE = (
    "\n\n**Come si accede.** Si invia un token Google a `POST /api/v1/auth/google` e si ottiene un token di sessione "
    "di 8 ore, da mandare come `Authorization: Bearer <token>` in tutte le altre richieste. L'utente deve essere "
    "registrato da un amministratore; il ruolo (admin, presale, viewer) decide cosa si può leggere e fare. In produzione "
    "la documentazione interattiva del server è spenta: questo file è una copia di sola lettura. Per provare le chiamate "
    "avvia il backend in locale (`make backend`) e apri `/docs`."
)


def _script_safe(text: str) -> str:
    """Codice o CSS dentro <script>/<style>: niente chiusure anticipate del tag."""
    return (
        text.replace("</script", "<\\/script")
        .replace("</style", "<\\/style")
        .replace("<!--", "<\\!--")
    )


def build_html(spec: dict, css: str, js: str, label: str) -> str:
    """Pagina unica: Swagger UI incorporato e schema dentro la pagina; nessuna richiesta di rete."""
    spec = copy.deepcopy(spec)
    spec["servers"] = [
        {
            "url": "https://INDIRIZZO-DEL-PORTALE",
            "description": "Sostituisci con l'indirizzo del portale",
        }
    ]
    spec.setdefault("info", {})["description"] = (
        spec["info"].get("description") or ""
    ) + ACCESS_NOTE
    # Lo schema è JSON dentro un <script>: il «<» si scrive \u003c, che resta JSON valido e non può chiudere il tag.
    spec_json = json.dumps(spec, ensure_ascii=False).replace("<", "\\u003c")
    return f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Portale Conti Economici - API</title>
<style>{_script_safe(css)}</style>
<style>body{{margin:0;font-family:system-ui,sans-serif}} .nota{{background:#0a0a0a;color:#fff;padding:12px 24px;font-size:14px;border-bottom:3px solid #00f5fe}} .nota b{{color:#00f5fe}}</style>
</head><body>
<div class="nota"><b>Portale CE · API</b> — copia di sola lettura dello schema (versione {label}). Le chiamate di prova si fanno in locale, non da questa pagina.</div>
<div id="swagger-ui"></div>
<script type="application/json" id="spec">{spec_json}</script>
<script>{_script_safe(js)}</script>
<script>
window.ui = SwaggerUIBundle({{ spec: JSON.parse(document.getElementById('spec').textContent), dom_id: '#swagger-ui',
  deepLinking: false, docExpansion: 'list', defaultModelsExpandDepth: 0, supportedSubmitMethods: [], presets: [SwaggerUIBundle.presets.apis] }});
</script></body></html>"""


def swagger_ui_files(workdir: Path) -> tuple[str, str]:
    """CSS e JavaScript di Swagger UI, scaricati con npm (pacchetto `swagger-ui-dist`)."""
    subprocess.run(
        ["npm", "pack", "swagger-ui-dist", "--silent", "--pack-destination", str(workdir)],
        check=True, cwd=workdir, capture_output=True,
    )  # fmt: skip
    with tarfile.open(next(workdir.glob("swagger-ui-dist-*.tgz"))) as tar:
        css = tar.extractfile("package/swagger-ui.css").read().decode("utf-8")  # type: ignore[union-attr]
        js = tar.extractfile("package/swagger-ui-bundle.js").read().decode("utf-8")  # type: ignore[union-attr]
    return css, js


def version_label() -> str:
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%h, %ad", "--date=format:%d/%m/%Y"],
            capture_output=True, text=True, check=True, cwd=ROOT,
        ).stdout.strip()  # fmt: skip
        return out or "senza versione"
    except (OSError, subprocess.CalledProcessError):
        return "senza versione"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=str(ROOT / "api-swagger.html"), help="file da scrivere")
    out = Path(parser.parse_args().out)
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        css, js = swagger_ui_files(Path(tmp))
    out.write_text(build_html(spec, css, js, version_label()), encoding="utf-8")
    operations = sum(
        1
        for p in spec["paths"].values()
        for m in p
        if m in {"get", "post", "put", "patch", "delete"}
    )
    print(
        f"Scritto {out} ({out.stat().st_size / 1e6:.1f} MB, {operations} operazioni). Si apre con un doppio clic."
    )


if __name__ == "__main__":
    main()
