"""Orquestación segura y reparación acotada de las salidas de triaje."""

import logging

from pydantic import ValidationError

from backend.app.providers import (
    ProviderConnectionError,
    ProviderOutput,
    ProviderRateLimitError,
    RepairContext,
    ToolCall,
    TriageProvider,
)
from backend.app.schemas import RiskMatrixObservation, TriageRequest, TriageResult
from backend.app.tools import (
    InvalidToolArgumentsError,
    RequiredToolCallError,
    RiskMatrixTool,
    ToolError,
    ToolStepLimitError,
)

from .errors import InvalidProviderOutputError

_MAX_REPAIR_ATTEMPTS = 3
_MAX_TOOL_STEPS = 1
_logger = logging.getLogger("iaviso.triage")


class TriageService:
    """Valida cada propuesta y solicita reparaciones hasta un límite estricto."""

    def __init__(
        self,
        provider: TriageProvider,
        *,
        max_repair_attempts: int = 1,
        risk_matrix_tool: RiskMatrixTool | None = None,
    ) -> None:
        if (
            isinstance(max_repair_attempts, bool)
            or not isinstance(max_repair_attempts, int)
            or not 0 <= max_repair_attempts <= _MAX_REPAIR_ATTEMPTS
        ):
            raise ValueError("max_repair_attempts debe estar entre 0 y 3.")
        self._provider = provider
        self._risk_matrix_tool = (
            risk_matrix_tool if risk_matrix_tool is not None else RiskMatrixTool()
        )
        self._max_repair_attempts = max_repair_attempts

    def triage(self, request: TriageRequest, *, request_id: str) -> TriageResult:
        observation: RiskMatrixObservation | None = None
        repair: RepairContext | None = None
        tool_call: ToolCall | None = None
        repairs_used = 0
        max_provider_steps = self._max_repair_attempts + _MAX_TOOL_STEPS + 1

        for step in range(1, max_provider_steps + 1):
            try:
                candidate = self._provider.generate(
                    request,
                    observation=observation,
                    repair=repair,
                    tool_call=tool_call,
                )
            except (ProviderConnectionError, ProviderRateLimitError) as exc:
                _logger.warning(
                    "triage_attempt",
                    extra={
                        "request_id": request_id,
                        "attempt": step,
                        "outcome": "provider_error",
                        "error_type": type(exc).__name__,
                    },
                )
                raise

            if isinstance(candidate, ToolCall):
                if observation is not None:
                    raise ToolStepLimitError(
                        "Solo se permite una consulta de matriz por triaje."
                    )
                if candidate.name != self._risk_matrix_tool.name:
                    raise InvalidToolArgumentsError(
                        "La herramienta solicitada no está permitida."
                    )
                try:
                    observation = self._risk_matrix_tool.execute(candidate.arguments)
                except ToolError as exc:
                    _logger.warning(
                        "tool_execution",
                        extra={
                            "request_id": request_id,
                            "step": step,
                            "tool_name": candidate.name,
                            "outcome": "rejected",
                            "error_type": type(exc).__name__,
                        },
                    )
                    raise
                _logger.info(
                    "tool_execution",
                    extra={
                        "request_id": request_id,
                        "step": step,
                        "tool_name": observation.tool_name,
                        "tool_arguments": observation.arguments.model_dump(),
                        "matrix_version": observation.matrix_version,
                        "tool_result": {
                            "rule_id": observation.rule_id,
                            "recommended_urgency": observation.recommended_urgency,
                            "department": observation.department,
                            "evidence": observation.evidence,
                        },
                        "outcome": "accepted",
                    },
                )
                tool_call = candidate
                repair = None
                continue

            if observation is None:
                raise RequiredToolCallError(
                    "El proveedor debe consultar la matriz antes de finalizar."
                )

            output_attempt = repairs_used + 1
            try:
                result = self._parse(candidate)
            except ValidationError as exc:
                _logger.warning(
                    "triage_attempt",
                    extra={
                        "request_id": request_id,
                        "attempt": output_attempt,
                        "outcome": "invalid_output",
                        "error_type": "ValidationError",
                    },
                )
                if repairs_used == self._max_repair_attempts:
                    raise InvalidProviderOutputError(attempts=output_attempt) from exc
                repairs_used += 1
                repair = RepairContext(
                    invalid_output=candidate,
                    validation_errors=self._summarize_errors(exc),
                )
                continue

            if result.category != observation.arguments.category:
                _logger.warning(
                    "triage_attempt",
                    extra={
                        "request_id": request_id,
                        "attempt": output_attempt,
                        "outcome": "invalid_output",
                        "error_type": "ToolEvidenceMismatch",
                    },
                )
                if repairs_used == self._max_repair_attempts:
                    raise InvalidProviderOutputError(attempts=output_attempt)
                repairs_used += 1
                repair = RepairContext(
                    invalid_output=candidate,
                    validation_errors=("category:tool_evidence_mismatch",),
                )
                continue

            _logger.info(
                "triage_attempt",
                extra={
                    "request_id": request_id,
                    "attempt": output_attempt,
                    "outcome": "accepted",
                },
            )
            return result

        raise ToolStepLimitError("Se agotó el límite total de pasos del triaje.")

    @staticmethod
    def _parse(candidate: ProviderOutput) -> TriageResult:
        if isinstance(candidate, (str, bytes)):
            return TriageResult.model_validate_json(candidate)
        return TriageResult.model_validate(candidate)

    @staticmethod
    def _summarize_errors(error: ValidationError) -> tuple[str, ...]:
        return tuple(
            (
                f"{'.'.join(str(part) for part in item['loc'])}:"
                f"{item['type']}:{item['msg']}"
            )
            for item in error.errors(include_url=False, include_context=False, include_input=False)
        )
