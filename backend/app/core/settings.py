"""Configuración validada de la aplicación."""

from functools import lru_cache
from pathlib import Path
from typing import Self

from pydantic import AnyHttpUrl, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Opciones seguras que pueden ajustarse mediante variables de entorno."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_path: Path = Path("data/local/iaviso.db")
    llm_repair_attempts: int = Field(default=1, ge=0, le=3)
    llm_max_retries: int = Field(default=2, ge=0, le=5)
    llm_retry_base_seconds: float = Field(default=0.5, ge=0, le=60)
    llm_retry_max_seconds: float = Field(default=8, ge=0, le=300)
    ollama_base_url: AnyHttpUrl = "http://127.0.0.1:11434"
    local_model: str = ""
    llm_timeout_seconds: float = Field(default=30, gt=0, le=300)
    ollama_temperature: float = Field(default=0, ge=0, le=2)
    ollama_top_p: float = Field(default=0.9, gt=0, le=1)
    external_api_base_url: AnyHttpUrl = (
        "https://generativelanguage.googleapis.com/v1beta"
    )
    external_api_key: SecretStr = SecretStr("")
    external_model: str = "gemini-3.5-flash-lite"
    external_temperature: float = Field(default=0, ge=0, le=2)
    external_top_p: float = Field(default=0.9, gt=0, le=1)

    @model_validator(mode="after")
    def validate_retry_window(self) -> Self:
        if self.llm_retry_base_seconds > self.llm_retry_max_seconds:
            raise ValueError(
                "LLM_RETRY_BASE_SECONDS no puede superar LLM_RETRY_MAX_SECONDS."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
