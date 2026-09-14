"""Contratos públicos para errores controlados de proveedor."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

ErrorCode = Literal[
    "comparison_not_found",
    "comparison_review_conflict",
    "notice_not_found",
    "persistence_error",
    "review_conflict",
    "request_validation_error",
    "invalid_provider_output",
    "provider_unavailable",
    "provider_rate_limited",
    "invalid_tool_arguments",
    "invalid_risk_matrix",
    "invalid_knowledge_base",
    "required_tool_not_executed",
    "tool_step_limit_exceeded",
]


class ValidationErrorDetail(BaseModel):
    """Detalle mínimo de validación que nunca contiene el valor recibido."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    loc: tuple[str | int, ...]
    type: str
    message: str


class ErrorDetail(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    code: ErrorCode
    message: str
    details: tuple[ValidationErrorDetail, ...] | None = None


class ErrorResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    error: ErrorDetail
    request_id: str
