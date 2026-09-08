"""Configuración validada de la aplicación."""

from functools import lru_cache

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Opciones seguras que pueden ajustarse mediante variables de entorno."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_repair_attempts: int = Field(default=1, ge=0, le=3)
    ollama_base_url: AnyHttpUrl = "http://127.0.0.1:11434"
    local_model: str = ""
    llm_timeout_seconds: float = Field(default=30, gt=0, le=300)
    ollama_temperature: float = Field(default=0, ge=0, le=2)
    ollama_top_p: float = Field(default=0.9, gt=0, le=1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
