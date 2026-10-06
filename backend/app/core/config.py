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

    # Email (Mailjet). "auto": in locale le email si scrivono nel log, altrove partono con Mailjet.
    mail_backend: Literal["auto", "console", "mailjet"] = "auto"
    mailjet_api_key: str | None = None
    mailjet_api_secret: str | None = None
    mailjet_url: str = "https://api.mailjet.com/v3.1/send"
    mailjet_sandbox: bool = False  # convalida le email senza consegnarle
    mail_from: str = "teamdata@huware.com"
    mail_from_name: str = "Portale Conti Economici"
    mail_timeout_seconds: float = 5.0
    mail_max_attempts: int = 5
    public_base_url: str = (
        "http://localhost:5173"  # indirizzo del portale usato nei link delle email
    )

    @field_validator("cors_origins", "allowed_email_domains", mode="before")
    @classmethod
    def split_lists(cls, v: object) -> object:
        return _split_csv(v)

    @field_validator("allowed_email_domains")
    @classmethod
    def lowercase_domains(cls, v: list[str]) -> list[str]:
        return [d.lower().lstrip("@") for d in v]

    @field_validator("public_base_url")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @field_validator("bootstrap_admin_email")
    @classmethod
    def lowercase_email(cls, v: str | None) -> str | None:
        return v.strip().lower() if v and v.strip() else None

    @property
    def effective_mail_backend(self) -> str:
        if self.mail_backend != "auto":
            return self.mail_backend
        return "console" if self.app_env == "local" else "mailjet"

    @model_validator(mode="after")
    def require_mailjet_credentials(self) -> "Settings":
        if self.effective_mail_backend == "mailjet" and not (
            self.mailjet_api_key and self.mailjet_api_secret
        ):
            raise ValueError(
                "MAILJET_API_KEY e MAILJET_API_SECRET sono obbligatorie con le email Mailjet "
                "(in alternativa MAIL_BACKEND=console)"
            )
        return self

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
