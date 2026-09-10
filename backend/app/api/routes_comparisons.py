"""Comparación trazable de ambos proveedores con una única entrada."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from backend.app.repositories import SQLiteNoticeRepository
from backend.app.schemas import (
    ComparisonProviderResult,
    ComparisonRequest,
    ComparisonResponse,
    TriageRequest,
)
from backend.app.services import MetricsService, TriageService, error_code_for

from .routes_triage import (
    get_metrics_service,
    get_notice_repository,
    get_triage_service,
)

router = APIRouter(prefix="/api/v1", tags=["comparisons"])


@router.post("/comparisons", response_model=ComparisonResponse)
def create_comparison(
    payload: ComparisonRequest,
    request: Request,
    service: Annotated[TriageService, Depends(get_triage_service)],
    metrics_service: Annotated[MetricsService, Depends(get_metrics_service)],
    repository: Annotated[
        SQLiteNoticeRepository,
        Depends(get_notice_repository),
    ],
) -> ComparisonResponse:
    results: list[ComparisonProviderResult] = []
    for provider in ("local", "external"):
        triage_request = TriageRequest(
            text=payload.text,
            location=payload.location,
            provider=provider,
        )
        execution = service.execute(
            triage_request,
            request_id=f"{request.state.request_id}:{provider}",
        )
        results.append(
            ComparisonProviderResult(
                provider=provider,
                result=execution.result,
                error_code=error_code_for(execution.error),
                metrics=metrics_service.build(
                    triage_request,
                    execution.telemetry,
                ),
            )
        )
    return repository.create_comparison(payload, tuple(results))
