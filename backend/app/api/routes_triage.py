"""Endpoint de triaje asistido con validación y herramienta acotada."""

from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from backend.app.core.settings import get_settings
from backend.app.providers import (
    GeminiTriageProvider,
    OllamaEmbeddingProvider,
    OllamaTriageProvider,
    ProviderRouter,
)
from backend.app.repositories import SQLiteNoticeRepository
from backend.app.schemas import ErrorResponse, TriageProposalResponse, TriageRequest
from backend.app.services import (
    MetricsService,
    PreventionKnowledgeRetriever,
    PrivacyService,
    SimilarityService,
    TriageService,
)

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
    knowledge_retriever=PreventionKnowledgeRetriever(
        _settings.knowledge_base_path,
        max_sources=_settings.rag_max_sources,
    ),
)
_metrics_service = MetricsService(_settings)
_privacy_service = PrivacyService()
_similarity_service = SimilarityService(
    OllamaEmbeddingProvider(
        base_url=str(_settings.ollama_base_url),
        model=_settings.embedding_model,
        timeout_seconds=_settings.embedding_timeout_seconds,
    ),
    enabled=_settings.embedding_enabled,
    model=_settings.embedding_model,
    threshold=_settings.embedding_threshold,
    top_k=_settings.embedding_top_k,
)


def get_triage_service() -> TriageService:
    """Dependencia sustituible para pruebas y futuros proveedores."""

    return _triage_service


def get_metrics_service() -> MetricsService:
    """Configuración única para convertir telemetría en métricas públicas."""

    return _metrics_service


def get_privacy_service() -> PrivacyService:
    """Limpia el aviso antes de cualquier proveedor o persistencia."""

    return _privacy_service


def get_similarity_service() -> SimilarityService:
    """Capacidad complementaria sustituible sin afectar al triaje."""

    return _similarity_service


@lru_cache
def get_notice_repository() -> SQLiteNoticeRepository:
    """Dependencia sustituible para usar bases temporales en pruebas."""

    return SQLiteNoticeRepository(_settings.database_path)


@router.post(
    "/triage",
    response_model=TriageProposalResponse,
    responses={
        429: {"model": ErrorResponse, "description": "Límite temporal del proveedor"},
        500: {
            "model": ErrorResponse,
            "description": "Matriz o corpus inválidos o no disponibles",
        },
        502: {"model": ErrorResponse, "description": "Salida del proveedor inválida"},
        503: {"model": ErrorResponse, "description": "Proveedor no disponible"},
    },
)
def create_triage(
    payload: TriageRequest,
    request: Request,
    service: Annotated[TriageService, Depends(get_triage_service)],
    privacy_service: Annotated[PrivacyService, Depends(get_privacy_service)],
    similarity_service: Annotated[
        SimilarityService,
        Depends(get_similarity_service),
    ],
    metrics_service: Annotated[MetricsService, Depends(get_metrics_service)],
    repository: Annotated[
        SQLiteNoticeRepository,
        Depends(get_notice_repository),
    ],
) -> TriageProposalResponse:
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
    execution = service.execute(sanitized_payload, request_id=request_id)
    metrics = metrics_service.build(
        sanitized_payload,
        execution.telemetry,
        evidence=execution.evidence,
    )
    if execution.error is not None:
        raise execution.error
    if execution.result is None:
        raise RuntimeError("La ejecución terminó sin resultado ni error.")
    similarity = similarity_service.analyze(
        sanitized_payload.text,
        sanitized_payload.location,
        repository,
        request_id=request_id,
    )
    response = repository.create_triage(
        sanitized_payload,
        execution.result,
        request_id=request_id,
        model=metrics.model,
        metrics=metrics,
        similarity=similarity.result,
        embedding=similarity.embedding,
    )
    return response.model_copy(update={"privacy": sanitized_notice.privacy})
