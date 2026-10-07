from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import SettingsDep

router = APIRouter(tags=["system"])


@router.get("/health", summary="Verifica che il servizio sia attivo")
def health() -> dict[str, str]:
    return {"status": "ok"}


class PublicConfig(BaseModel):
    google_client_id: str | None
    dev_login: bool


@router.get(
    "/config", response_model=PublicConfig, summary="Configurazione pubblica per il frontend"
)
def public_config(settings: SettingsDep) -> PublicConfig:
    """Il frontend la legge all'avvio: così la stessa immagine vale per test e produzione.

    Contiene solo ciò che il browser deve già sapere (l'ID client OAuth è pubblico per natura).
    L'accesso simulato esiste solo con APP_ENV=local.
    """
    return PublicConfig(
        google_client_id=settings.google_oauth_client_id, dev_login=settings.app_env == "local"
    )
