from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurazione letta da variabili d'ambiente (o file .env in locale)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"  # local | test | prod
    database_url: str = "postgresql+psycopg://ceportal:ceportal@localhost:5432/ceportal"
    cors_origins: list[str] = ["http://localhost:5173"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip().startswith("["):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
