"""Traducción estable de errores de dominio a respuestas HTTP."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.app.providers import ProviderConnectionError, ProviderRateLimitError
from backend.app.schemas import ErrorDetail, ErrorResponse
from backend.app.services import InvalidProviderOutputError
from backend.app.tools import (
    InvalidRiskMatrixError,
    InvalidToolArgumentsError,
    RequiredToolCallError,
    ToolStepLimitError,
)


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    request_id = request.state.request_id
    payload = ErrorResponse(
        error=ErrorDetail(code=code, message=message),
        request_id=request_id,
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(),
        headers=headers,
    )


def register_exception_handlers(application: FastAPI) -> None:
    """Registra solo fallos previstos; los detalles internos no salen por HTTP."""

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
