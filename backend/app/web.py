"""Il frontend compilato, servito dallo stesso servizio dell'API (un solo servizio per ambiente)."""

import mimetypes
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, Response

mimetypes.add_type("font/woff2", ".woff2")

# assets/: file con l'impronta nel nome, non cambiano mai
IMMUTABLE = "public, max-age=31536000, immutable"
SHORT = "public, max-age=3600"
NO_CACHE = "no-cache"  # index.html: va riletta a ogni visita, così punta sempre ai file giusti


def mount_frontend(app: FastAPI, static_dir: Path) -> None:
    root = static_dir.resolve()
    index = root / "index.html"
    if not index.is_file():
        raise RuntimeError(f"STATIC_DIR non contiene il frontend compilato (manca {index})")

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def frontend(path: str) -> Response:
        if path == "api" or path.startswith("api/"):
            return JSONResponse(
                {"detail": "Non trovato"}, status_code=404
            )  # le API sbagliate non danno una pagina HTML
        if path:
            candidate = (root / path).resolve()
            if candidate.is_file() and candidate.is_relative_to(
                root
            ):  # niente uscite dalla cartella (../)
                cache = IMMUTABLE if candidate.is_relative_to(root / "assets") else SHORT
                return FileResponse(candidate, headers={"Cache-Control": cache})
            if Path(
                path
            ).suffix:  # un file che non esiste è un 404, non la pagina dell'applicazione
                return JSONResponse({"detail": "Non trovato"}, status_code=404)
        # qualunque altro indirizzo è una pagina dell'applicazione (/ce/123, /admin/utenti…)
        return FileResponse(index, headers={"Cache-Control": NO_CACHE})
