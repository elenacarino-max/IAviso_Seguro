"""Endpoint de disponibilidad de la API, modelos y persistencia."""

from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.core.settings import get_settings
from backend.app.schemas import HealthResponse
from backend.app.services import HealthService

from .routes_triage import get_notice_repository

router = APIRouter(tags=["health"])


@lru_cache
def get_health_service() -> HealthService:
    """Construye una única sonda con clientes HTTP reutilizables."""

    return HealthService(get_settings(), get_notice_repository())


@router.get("/health", response_model=HealthResponse)
def health(
    service: Annotated[HealthService, Depends(get_health_service)],
) -> HealthResponse:
    return service.check()
