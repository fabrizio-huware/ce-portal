import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.api.v1 import api_router
from app.api.v1 import auth as auth_routes
from app.core.config import Settings, get_settings
from app.services.bootstrap import ensure_bootstrap_admin

logger = logging.getLogger("ce_portal")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if settings.bootstrap_admin_email:
            from app.db.session import SessionLocal

            try:
                with SessionLocal() as session:
                    if ensure_bootstrap_admin(session, settings.bootstrap_admin_email):
                        logger.warning("Creato l'amministratore iniziale")
            except Exception:
                logger.exception("Impossibile creare l'amministratore iniziale")
        yield

    app = FastAPI(
        title="Portale Conti Economici",
        version="0.1.0",
        description="API per la gestione dei Conti Economici (CE) di progetto.",
        openapi_url="/api/v1/openapi.json",
        docs_url="/docs",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(_: Request, exc: IntegrityError) -> JSONResponse:
        # Rete di sicurezza per le gare tra richieste: i casi normali sono già controllati prima.
        logger.warning("Violazione di integrità: %s", exc.orig)
        return JSONResponse(status_code=409, content={"detail": "Conflitto con dati esistenti"})

    app.include_router(api_router, prefix="/api/v1")
    if settings.app_env == "local":
        app.include_router(auth_routes.dev_router, prefix="/api/v1")
    return app


app = create_app()
