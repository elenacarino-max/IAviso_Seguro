"""Endpoint de triaje de la Fase 1."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from backend.app.core.settings import get_settings
from backend.app.providers import MockTriageProvider
from backend.app.schemas import ErrorResponse, TriageRequest, TriageResult
from backend.app.services import TriageService

router = APIRouter(prefix="/api/v1", tags=["triage"])

_settings = get_settings()
_triage_service = TriageService(
    MockTriageProvider(),
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
