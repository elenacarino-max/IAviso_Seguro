"""Comparación trazable de ambos proveedores con una única entrada."""

from concurrent.futures import ThreadPoolExecutor
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from backend.app.repositories import SQLiteNoticeRepository
from backend.app.schemas import (
    ComparisonProviderResult,
    ComparisonRequest,
    ComparisonReviewRecord,
    ComparisonReviewRequest,
    ComparisonResponse,
    TriageRequest,
)
from backend.app.services import (
    MetricsService,
    PrivacyService,
    TriageService,
    error_code_for,
)

from .routes_triage import (
    get_metrics_service,
    get_notice_repository,
    get_privacy_service,
    get_triage_service,
)

router = APIRouter(prefix="/api/v1", tags=["comparisons"])


@router.post("/comparisons", response_model=ComparisonResponse)
def create_comparison(
    payload: ComparisonRequest,
    request: Request,
    service: Annotated[TriageService, Depends(get_triage_service)],
    privacy_service: Annotated[PrivacyService, Depends(get_privacy_service)],
    metrics_service: Annotated[MetricsService, Depends(get_metrics_service)],
    repository: Annotated[
        SQLiteNoticeRepository,
        Depends(get_notice_repository),
    ],
) -> ComparisonResponse:
    request_id = request.state.request_id
    sanitized_notice = privacy_service.sanitize_notice(
        payload.text,
        payload.location,
    )
    sanitized_payload = payload.model_copy(
        update={
            "text": sanitized_notice.text,
            "location": sanitized_notice.location,
        }
    )

    def execute_provider(provider: str) -> ComparisonProviderResult:
        triage_request = TriageRequest(
            text=sanitized_payload.text,
            location=sanitized_payload.location,
            provider=provider,
        )
        execution = service.execute(
            triage_request,
            request_id=f"{request_id}:{provider}",
        )
        return ComparisonProviderResult(
            provider=provider,
            result=execution.result,
            error_code=error_code_for(execution.error),
            metrics=metrics_service.build(
                triage_request,
                execution.telemetry,
                evidence=execution.evidence,
            ),
        )

    providers = ("local", "external")
    with ThreadPoolExecutor(
        max_workers=len(providers),
        thread_name_prefix="comparison-provider",
    ) as executor:
        # Enviar ambos trabajos antes de esperar evita que Ollama bloquee el
        # inicio de Gemini (o al revés) y reduce la latencia total al máximo de
        # ambos proveedores, en vez de a su suma.
        futures = {
            provider: executor.submit(execute_provider, provider)
            for provider in providers
        }
        # La lectura respeta el orden público local/external aunque cada futuro
        # termine en un instante distinto; así la API y la interfaz son estables.
        results = tuple(futures[provider].result() for provider in providers)
    response = repository.create_comparison(sanitized_payload, results)
    return response.model_copy(update={"privacy": sanitized_notice.privacy})


@router.post(
    "/comparisons/{comparison_id}/review",
    response_model=ComparisonReviewRecord,
    responses={
        404: {"description": "Comparación no encontrada"},
        409: {"description": "La comparación ya fue revisada"},
    },
)
def review_comparison(
    comparison_id: UUID,
    payload: ComparisonReviewRequest,
    repository: Annotated[
        SQLiteNoticeRepository,
        Depends(get_notice_repository),
    ],
) -> ComparisonReviewRecord:
    """Guarda una única clasificación humana de referencia."""

    return repository.review_comparison(comparison_id, payload)
