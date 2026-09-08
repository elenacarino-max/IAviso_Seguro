"""Contratos públicos para errores controlados de proveedor."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

ErrorCode = Literal[
    "invalid_provider_output",
    "provider_unavailable",
    "provider_rate_limited",
]


class ErrorDetail(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    code: ErrorCode
    message: str


class ErrorResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    error: ErrorDetail
    request_id: str
