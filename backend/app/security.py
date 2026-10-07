"""Intestazioni di sicurezza su tutte le risposte."""

from fastapi import FastAPI, Request

from app.core.config import Settings

# Google Identity Services (accesso con Google) richiede questi indirizzi; il resto è tutto «self»
# (il font è incluso nel portale, nessuna risorsa esterna).
CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self' https://accounts.google.com/gsi/client",
        "style-src 'self' 'unsafe-inline' https://accounts.google.com/gsi/style",
        "img-src 'self' data: https://*.googleusercontent.com",
        "font-src 'self'",
        "connect-src 'self' https://accounts.google.com/gsi/",
        "frame-src https://accounts.google.com/gsi/",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
        "object-src 'none'",
    ]
)
NO_CSP = ("/docs", "/redoc")  # le pagine di documentazione caricano script da un CDN


def add_security_headers(app: FastAPI, settings: Settings) -> None:
    @app.middleware("http")
    async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if settings.app_env != "local":
            h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        path = request.url.path
        if path.startswith("/api/"):
            h.setdefault("Cache-Control", "no-store")  # dati riservati: mai in una cache condivisa
        if not path.startswith(NO_CSP):
            h.setdefault("Content-Security-Policy", CSP)
        return response
