"""Contratos de disponibilidad de la API y sus dependencias."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ServiceId = Literal[
    "api",
    "ollama",
    "gemini",
    "sqlite",
    "risk_matrix",
    "rag",
    "embeddings",
]
ServiceStatus = Literal[
    "available",
    "unavailable",
    "not_configured",
    "disabled",
]


class ServiceHealth(BaseModel):
    """Estado público y seguro de un componente de la arquitectura."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    id: ServiceId
    label: str = Field(min_length=1, max_length=100)
    status: ServiceStatus
    detail: str | None = Field(default=None, min_length=1, max_length=100)


class HealthResponse(BaseModel):
    """FastAPI está atendiendo y expone el estado de sus dependencias."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    status: Literal["ok", "degraded"] = "ok"
    services: tuple[ServiceHealth, ...]
