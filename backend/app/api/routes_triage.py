"""Endpoint de triaje de la Fase 1."""

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.providers import MockTriageProvider
from backend.app.schemas import TriageRequest, TriageResult
from backend.app.services import TriageService

router = APIRouter(prefix="/api/v1", tags=["triage"])

_triage_service = TriageService(MockTriageProvider())


def get_triage_service() -> TriageService:
    """Dependencia sustituible para pruebas y futuros proveedores reales."""

    return _triage_service


@router.post("/triage", response_model=TriageResult)
def create_triage(
    request: TriageRequest,
    service: Annotated[TriageService, Depends(get_triage_service)],
) -> TriageResult:
    return service.triage(request)
