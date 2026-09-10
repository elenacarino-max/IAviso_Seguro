"""Contratos públicos para errores controlados de proveedor."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

ErrorCode = Literal[
    "notice_not_found",
    "persistence_error",
    "review_conflict",
    "invalid_provider_output",
    "provider_unavailable",
    "provider_rate_limited",
    "invalid_tool_arguments",
    "invalid_risk_matrix",
    "required_tool_not_executed",
    "tool_step_limit_exceeded",
]


class ErrorDetail(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    code: ErrorCode
    message: str


class ErrorResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    error: ErrorDetail
    request_id: str
