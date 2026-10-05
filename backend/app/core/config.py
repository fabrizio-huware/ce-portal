from functools import lru_cache
from typing import Annotated, Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

DEFAULT_DEV_SECRET = "dev-only-insecure-secret-do-not-use-in-cloud-0123456789"


def _split_csv(value: object) -> object:
    """Accetta 'a,b,c' (variabili d'ambiente) oppure una lista."""
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


class Settings(BaseSettings):
    """Configurazione letta da variabili d'ambiente (o file .env in locale)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["local", "test", "prod"] = "local"
    database_url: str = "postgresql+psycopg://ceportal:ceportal@localhost:5432/ceportal"
    # NoDecode: i valori si scrivono 'a,b' nelle variabili d'ambiente, non come JSON.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    # Autenticazione
    jwt_secret: str = DEFAULT_DEV_SECRET
    jwt_expire_minutes: int = 480
    google_oauth_client_id: str | None = None
    allowed_email_domains: Annotated[list[str], NoDecode] = ["huware.com"]
    bootstrap_admin_email: str | None = None

    @field_validator("cors_origins", "allowed_email_domains", mode="before")
    @classmethod
    def split_lists(cls, v: object) -> object:
        return _split_csv(v)

    @field_validator("allowed_email_domains")
    @classmethod
    def lowercase_domains(cls, v: list[str]) -> list[str]:
        return [d.lower().lstrip("@") for d in v]

    @field_validator("bootstrap_admin_email")
    @classmethod
    def lowercase_email(cls, v: str | None) -> str | None:
        return v.strip().lower() if v and v.strip() else None

    @model_validator(mode="after")
    def require_real_secret_outside_local(self) -> "Settings":
        if self.app_env != "local" and (
            self.jwt_secret == DEFAULT_DEV_SECRET or len(self.jwt_secret) < 32
        ):
            raise ValueError(
                "JWT_SECRET deve essere impostato (almeno 32 caratteri) fuori dall'ambiente local"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
