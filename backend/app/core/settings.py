"""Configuración validada de la aplicación."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Opciones seguras que pueden ajustarse mediante variables de entorno."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_repair_attempts: int = Field(default=1, ge=0, le=3)


@lru_cache
def get_settings() -> Settings:
    return Settings()
