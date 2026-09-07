"""Contrato de la comprobación básica de disponibilidad."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Respuesta mínima que confirma que FastAPI está atendiendo."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    status: Literal["ok"] = "ok"
