"""Orquestación segura y reparación acotada de las salidas de triaje."""

import logging

from pydantic import ValidationError

from backend.app.providers import (
    ProviderConnectionError,
    ProviderOutput,
    ProviderRateLimitError,
    RepairContext,
    TriageProvider,
)
from backend.app.schemas import TriageRequest, TriageResult

from .errors import InvalidProviderOutputError

_MAX_REPAIR_ATTEMPTS = 3
_logger = logging.getLogger("iaviso.triage")


class TriageService:
    """Valida cada propuesta y solicita reparaciones hasta un límite estricto."""

    def __init__(
        self,
        provider: TriageProvider,
        *,
        max_repair_attempts: int = 1,
    ) -> None:
        if (
            isinstance(max_repair_attempts, bool)
            or not isinstance(max_repair_attempts, int)
            or not 0 <= max_repair_attempts <= _MAX_REPAIR_ATTEMPTS
        ):
            raise ValueError("max_repair_attempts debe estar entre 0 y 3.")
        self._provider = provider
        self._max_repair_attempts = max_repair_attempts

    def triage(self, request: TriageRequest, *, request_id: str) -> TriageResult:
        repair: RepairContext | None = None
        total_attempts = self._max_repair_attempts + 1

        for attempt in range(1, total_attempts + 1):
            try:
                candidate = self._provider.generate(request, repair=repair)
            except (ProviderConnectionError, ProviderRateLimitError) as exc:
                _logger.warning(
                    "triage_attempt",
                    extra={
                        "request_id": request_id,
                        "attempt": attempt,
                        "outcome": "provider_error",
                        "error_type": type(exc).__name__,
                    },
                )
                raise

            try:
                result = self._parse(candidate)
            except ValidationError as exc:
                _logger.warning(
                    "triage_attempt",
                    extra={
                        "request_id": request_id,
                        "attempt": attempt,
                        "outcome": "invalid_output",
                        "error_type": "ValidationError",
                    },
                )
                if attempt == total_attempts:
                    raise InvalidProviderOutputError(attempts=attempt) from exc
                repair = RepairContext(
                    invalid_output=candidate,
                    validation_errors=self._summarize_errors(exc),
                )
                continue

            _logger.info(
                "triage_attempt",
                extra={
                    "request_id": request_id,
                    "attempt": attempt,
                    "outcome": "accepted",
                },
            )
            return result

        raise AssertionError("El bucle de reparación debe devolver o lanzar un error.")

    @staticmethod
    def _parse(candidate: ProviderOutput) -> TriageResult:
        if isinstance(candidate, (str, bytes)):
            return TriageResult.model_validate_json(candidate)
        return TriageResult.model_validate(candidate)

    @staticmethod
    def _summarize_errors(error: ValidationError) -> tuple[str, ...]:
        return tuple(
            f"{'.'.join(str(part) for part in item['loc'])}:{item['type']}"
            for item in error.errors(include_url=False, include_context=False, include_input=False)
        )
