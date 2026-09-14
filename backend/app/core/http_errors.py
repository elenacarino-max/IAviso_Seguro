"""Traducción estable de errores de dominio a respuestas HTTP."""

import re

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.app.providers import ProviderConnectionError, ProviderRateLimitError
from backend.app.repositories import (
    ComparisonNotFoundError,
    ComparisonReviewConflictError,
    NoticeNotFoundError,
    PersistenceError,
    ReviewConflictError,
)
from backend.app.schemas import (
    ErrorCode,
    ErrorDetail,
    ErrorResponse,
    ValidationErrorDetail,
)
from backend.app.services import InvalidKnowledgeBaseError, InvalidProviderOutputError
from backend.app.tools import (
    InvalidRiskMatrixError,
    InvalidToolArgumentsError,
    RequiredToolCallError,
    ToolStepLimitError,
)

_SAFE_LOCATION_PARTS = frozenset(
    {
        "body",
        "query",
        "path",
        "header",
        "cookie",
        "text",
        "provider",
        "location",
        "decision",
        "reviewer",
        "comment",
        "expected_version",
        "category",
        "urgency",
        "department",
        "comparison_id",
        "notice_id",
        "search",
        "status",
        "closed",
        "review_priority",
        "order",
        "page",
        "limit",
        "window_days",
    }
)
_SAFE_ERROR_TYPE = re.compile(r"^[a-z0-9_.]{1,100}$")


def _safe_validation_location(value: object) -> tuple[str | int, ...]:
    """Conserva rutas conocidas y oculta nombres de campos aportados por el cliente."""

    if not isinstance(value, (list, tuple)):
        return ("request",)
    return tuple(
        part
        if (
            isinstance(part, int)
            and not isinstance(part, bool)
            or isinstance(part, str)
            and part in _SAFE_LOCATION_PARTS
        )
        else "<field>"
        for part in value
    )


def _safe_validation_details(
    exc: RequestValidationError,
) -> tuple[ValidationErrorDetail, ...]:
    """Proyecta los errores nativos sobre una lista blanca sin input, ctx ni msg."""

    details: list[ValidationErrorDetail] = []
    for error in exc.errors():
        error_type = error.get("type")
        details.append(
            ValidationErrorDetail(
                loc=_safe_validation_location(error.get("loc")),
                type=(
                    error_type
                    if isinstance(error_type, str)
                    and _SAFE_ERROR_TYPE.fullmatch(error_type)
                    else "validation_error"
                ),
                message="El campo no cumple el contrato de entrada.",
            )
        )
    return tuple(details)


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: ErrorCode,
    message: str,
    details: tuple[ValidationErrorDetail, ...] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    request_id = request.state.request_id
    payload = ErrorResponse(
        error=ErrorDetail(code=code, message=message, details=details),
        request_id=request_id,
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json", exclude_none=True),
        headers=headers,
    )


def register_exception_handlers(application: FastAPI) -> None:
    """Registra solo fallos previstos; los detalles internos no salen por HTTP."""

    @application.exception_handler(RequestValidationError)
    async def request_validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=422,
            code="request_validation_error",
            message="La petición contiene datos inválidos.",
            details=_safe_validation_details(exc),
        )

    @application.exception_handler(ComparisonNotFoundError)
    async def comparison_not_found_handler(
        request: Request,
        exc: ComparisonNotFoundError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=404,
            code="comparison_not_found",
            message="La comparación solicitada no existe.",
        )

    @application.exception_handler(ComparisonReviewConflictError)
    async def comparison_review_conflict_handler(
        request: Request,
        exc: ComparisonReviewConflictError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=409,
            code="comparison_review_conflict",
            message="La comparación ya tiene una referencia humana.",
        )

    @application.exception_handler(NoticeNotFoundError)
    async def notice_not_found_handler(
        request: Request,
        exc: NoticeNotFoundError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=404,
            code="notice_not_found",
            message="El aviso solicitado no existe.",
        )

    @application.exception_handler(ReviewConflictError)
    async def review_conflict_handler(
        request: Request,
        exc: ReviewConflictError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=409,
            code="review_conflict",
            message="La propuesta ya cambió o fue revisada.",
        )

    @application.exception_handler(PersistenceError)
    async def persistence_error_handler(
        request: Request,
        exc: PersistenceError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=500,
            code="persistence_error",
            message="No se pudo completar la operación de persistencia.",
        )

    @application.exception_handler(InvalidProviderOutputError)
    async def invalid_output_handler(
        request: Request,
        exc: InvalidProviderOutputError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=502,
            code="invalid_provider_output",
            message="El proveedor devolvió una respuesta inválida.",
        )

    @application.exception_handler(ProviderConnectionError)
    async def provider_connection_handler(
        request: Request,
        exc: ProviderConnectionError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=503,
            code="provider_unavailable",
            message="El proveedor no está disponible temporalmente.",
        )

    @application.exception_handler(ProviderRateLimitError)
    async def provider_rate_limit_handler(
        request: Request,
        exc: ProviderRateLimitError,
    ) -> JSONResponse:
        headers = None
        if exc.retry_after_seconds is not None:
            headers = {"Retry-After": str(exc.retry_after_seconds)}
        return _error_response(
            request,
            status_code=429,
            code="provider_rate_limited",
            message="El proveedor ha alcanzado temporalmente su límite.",
            headers=headers,
        )

    @application.exception_handler(InvalidToolArgumentsError)
    async def invalid_tool_arguments_handler(
        request: Request,
        exc: InvalidToolArgumentsError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=502,
            code="invalid_tool_arguments",
            message="El proveedor solicitó una herramienta o categoría inválida.",
        )

    @application.exception_handler(InvalidRiskMatrixError)
    async def invalid_risk_matrix_handler(
        request: Request,
        exc: InvalidRiskMatrixError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=500,
            code="invalid_risk_matrix",
            message="La matriz de riesgos no está disponible o es inválida.",
        )

    @application.exception_handler(InvalidKnowledgeBaseError)
    async def invalid_knowledge_base_handler(
        request: Request,
        exc: InvalidKnowledgeBaseError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=500,
            code="invalid_knowledge_base",
            message="La base documental preventiva no está disponible o es inválida.",
        )

    @application.exception_handler(RequiredToolCallError)
    async def required_tool_call_handler(
        request: Request,
        exc: RequiredToolCallError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=502,
            code="required_tool_not_executed",
            message="El proveedor no consultó la herramienta requerida.",
        )

    @application.exception_handler(ToolStepLimitError)
    async def tool_step_limit_handler(
        request: Request,
        exc: ToolStepLimitError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=502,
            code="tool_step_limit_exceeded",
            message="El proveedor superó el límite de acciones permitido.",
        )
