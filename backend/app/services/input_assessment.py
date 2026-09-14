"""Orquestación mínima del precheck, aislada del triaje definitivo."""

import logging
from collections.abc import Mapping

from backend.app.providers.input_assessment import InputAssessmentProvider
from backend.app.schemas.input_assessment import (
    InputAssessmentDecision,
    InputAssessmentRequest,
    InputAssessmentResponse,
)

_logger = logging.getLogger("iaviso.input_assessment")


class InputAssessmentService:
    """Valida una única respuesta sin matriz, RAG, métricas ni persistencia."""

    def __init__(self, provider: InputAssessmentProvider) -> None:
        self._provider = provider

    def assess(
        self,
        request: InputAssessmentRequest,
        *,
        request_id: str,
    ) -> InputAssessmentResponse:
        try:
            candidate = self._provider.assess(request)
            decision = self._parse(candidate)
        except Exception as exc:  # El precheck es complementario y falla abierto.
            _logger.warning(
                "input_assessment_unavailable",
                extra={
                    "request_id": request_id,
                    "provider": request.provider,
                    "error_type": type(exc).__name__,
                },
            )
            return InputAssessmentResponse(available=False, sufficient=None)

        _logger.info(
            "input_assessment_completed",
            extra={
                "request_id": request_id,
                "provider": request.provider,
                "sufficient": decision.sufficient,
                "question_count": len(decision.questions),
                "missing_aspects": list(decision.missing_aspects),
            },
        )
        return InputAssessmentResponse(
            available=True,
            sufficient=decision.sufficient,
            questions=decision.questions,
            missing_aspects=decision.missing_aspects,
        )

    @staticmethod
    def _parse(candidate: str | bytes | Mapping[str, object]) -> InputAssessmentDecision:
        if isinstance(candidate, (str, bytes)):
            return InputAssessmentDecision.model_validate_json(candidate)
        return InputAssessmentDecision.model_validate(candidate)
