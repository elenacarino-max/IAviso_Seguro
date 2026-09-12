"""Métricas agregadas para evaluar los proveedores del MVP."""

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.repositories import SQLiteNoticeRepository
from backend.app.schemas import MetricsSummary
from backend.app.services import MetricsSummaryService

from .routes_triage import get_notice_repository

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])


def get_metrics_summary_service() -> MetricsSummaryService:
    return MetricsSummaryService()


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
