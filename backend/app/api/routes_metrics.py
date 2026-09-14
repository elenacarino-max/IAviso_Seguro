"""Métricas agregadas de rendimiento IA y panorama preventivo."""

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.repositories import SQLiteNoticeRepository
from backend.app.schemas import (
    MetricsSummary,
    PreventiveAnalyticsResponse,
    PreventiveWindow,
)
from backend.app.services import MetricsSummaryService, PreventiveAnalyticsService

from .routes_triage import get_notice_repository

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])


def get_metrics_summary_service() -> MetricsSummaryService:
    return MetricsSummaryService()


def get_preventive_analytics_service() -> PreventiveAnalyticsService:
    return PreventiveAnalyticsService()


@router.get("/summary", response_model=MetricsSummary)
def get_metrics_summary(
    repository: Annotated[SQLiteNoticeRepository, Depends(get_notice_repository)],
    service: Annotated[MetricsSummaryService, Depends(get_metrics_summary_service)],
) -> MetricsSummary:
    """Resume flujo, rendimiento, estabilidad, coste y acuerdo humano."""

    return service.summarize(
        repository.list_notices(),
        repository.list_comparisons(),
    )


@router.get("/preventive", response_model=PreventiveAnalyticsResponse)
def get_preventive_analytics(
    repository: Annotated[SQLiteNoticeRepository, Depends(get_notice_repository)],
    service: Annotated[
        PreventiveAnalyticsService,
        Depends(get_preventive_analytics_service),
    ],
    window_days: PreventiveWindow = "30",
) -> PreventiveAnalyticsResponse:
    """Agrega hechos preventivos confirmados y carga operativa pendiente."""

    return service.summarize(repository.list_notices(), window_days)
