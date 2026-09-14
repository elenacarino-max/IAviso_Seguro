"""Endpoint no persistente para comprobar suficiencia antes del triaje."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from backend.app.core.settings import get_settings
from backend.app.providers.input_assessment import (
    GeminiInputAssessmentProvider,
    InputAssessmentProviderRouter,
    OllamaInputAssessmentProvider,
)
from backend.app.schemas import InputAssessmentRequest, InputAssessmentResponse
from backend.app.services import InputAssessmentService, PrivacyService

from .routes_triage import get_privacy_service

router = APIRouter(prefix="/api/v1", tags=["triage"])

_settings = get_settings()
_input_assessment_service = InputAssessmentService(
    InputAssessmentProviderRouter(
        {
            "local": OllamaInputAssessmentProvider(
                base_url=str(_settings.ollama_base_url),
                model=_settings.local_model,
                timeout_seconds=_settings.llm_timeout_seconds,
                temperature=_settings.ollama_temperature,
                top_p=_settings.ollama_top_p,
            ),
            "external": GeminiInputAssessmentProvider(
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
    )
)


def get_input_assessment_service() -> InputAssessmentService:
    """Dependencia sustituible para pruebas sin proveedores reales."""

    return _input_assessment_service


@router.post("/triage/precheck", response_model=InputAssessmentResponse)
def precheck_triage_input(
    payload: InputAssessmentRequest,
    request: Request,
    service: Annotated[
        InputAssessmentService,
        Depends(get_input_assessment_service),
    ],
    privacy_service: Annotated[PrivacyService, Depends(get_privacy_service)],
) -> InputAssessmentResponse:
    """Anonimiza y comprueba; no toca matriz, RAG, embeddings ni SQLite."""

    sanitized = privacy_service.sanitize_notice(payload.text, payload.location)
    sanitized_payload = payload.model_copy(
        update={"text": sanitized.text, "location": sanitized.location}
    )
    result = service.assess(
        sanitized_payload,
        request_id=request.state.request_id,
    )
    return result.model_copy(update={"privacy": sanitized.privacy})
