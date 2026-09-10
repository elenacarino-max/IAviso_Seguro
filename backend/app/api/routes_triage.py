"""Endpoint de triaje asistido con validación y herramienta acotada."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from backend.app.core.settings import get_settings
from backend.app.providers import (
    GeminiTriageProvider,
    OllamaTriageProvider,
    ProviderRouter,
)
from backend.app.schemas import ErrorResponse, TriageRequest, TriageResult
from backend.app.services import TriageService

router = APIRouter(prefix="/api/v1", tags=["triage"])

_settings = get_settings()
_triage_service = TriageService(
    ProviderRouter(
        {
            "local": OllamaTriageProvider(
                base_url=str(_settings.ollama_base_url),
                model=_settings.local_model,
                timeout_seconds=_settings.llm_timeout_seconds,
                temperature=_settings.ollama_temperature,
                top_p=_settings.ollama_top_p,
            ),
            "external": GeminiTriageProvider(
                base_url=str(_settings.external_api_base_url),
                api_key=_settings.external_api_key.get_secret_value(),
                model=_settings.external_model,
                timeout_seconds=_settings.llm_timeout_seconds,
                temperature=_settings.external_temperature,
                top_p=_settings.external_top_p,
                max_retries=_settings.llm_max_retries,
                retry_base_seconds=_settings.llm_retry_base_seconds,
                retry_max_seconds=_settings.llm_retry_max_seconds,
            ),
        }
    ),
    max_repair_attempts=_settings.llm_repair_attempts,
)


def get_triage_service() -> TriageService:
    """Dependencia sustituible para pruebas y futuros proveedores."""

    return _triage_service


@router.post(
    "/triage",
    response_model=TriageResult,
    responses={
        429: {"model": ErrorResponse, "description": "Límite temporal del proveedor"},
        500: {"model": ErrorResponse, "description": "Matriz inválida o no disponible"},
        502: {"model": ErrorResponse, "description": "Salida del proveedor inválida"},
        503: {"model": ErrorResponse, "description": "Proveedor no disponible"},
    },
)
def create_triage(
    payload: TriageRequest,
    request: Request,
    service: Annotated[TriageService, Depends(get_triage_service)],
) -> TriageResult:
    return service.triage(payload, request_id=request.state.request_id)
