"""Orquestación segura y reparación acotada de las salidas de triaje."""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from time import perf_counter

from pydantic import ValidationError

from backend.app.providers import (
    ProviderConnectionError,
    ProviderCallMetrics,
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
from .execution import ExecutionAccumulator, TriageExecution

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
        clock: Callable[[], float] = perf_counter,
        utc_clock: Callable[[], datetime] | None = None,
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
        self._clock = clock
        self._utc_clock = utc_clock or (lambda: datetime.now(UTC))

    def triage(self, request: TriageRequest, *, request_id: str) -> TriageResult:
        execution = self.execute(request, request_id=request_id)
        if execution.error is not None:
            raise execution.error
        if execution.result is None:
            raise RuntimeError("La ejecución terminó sin resultado ni error.")
        return execution.result

    def execute(self, request: TriageRequest, *, request_id: str) -> TriageExecution:
        accumulator = ExecutionAccumulator(
            started_at=self._utc_now(),
            started_tick=self._clock(),
        )
        try:
            result = self._triage(
                request,
                request_id=request_id,
                accumulator=accumulator,
            )
        except (
            InvalidProviderOutputError,
            ProviderConnectionError,
            ProviderRateLimitError,
            ToolError,
        ) as exc:
            return TriageExecution(
                result=None,
                telemetry=accumulator.finish(
                    completed_at=self._utc_now(),
                    completed_tick=self._clock(),
                    success=False,
                    error_type=type(exc).__name__,
                    json_valid=(
                        False
                        if isinstance(exc, InvalidProviderOutputError)
                        else None
                    ),
                ),
                error=exc,
            )
        return TriageExecution(
            result=result,
            telemetry=accumulator.finish(
                completed_at=self._utc_now(),
                completed_tick=self._clock(),
                success=True,
                error_type=None,
            ),
        )

    def _triage(
        self,
        request: TriageRequest,
        *,
        request_id: str,
        accumulator: ExecutionAccumulator,
    ) -> TriageResult:
        observation: RiskMatrixObservation | None = None
        repair: RepairContext | None = None
        tool_call: ToolCall | None = None
        repairs_used = 0
        max_provider_steps = self._max_repair_attempts + _MAX_TOOL_STEPS + 1

        for step in range(1, max_provider_steps + 1):
            provider_started = self._clock()
            try:
                candidate = self._provider.generate(
                    request,
                    observation=observation,
                    repair=repair,
                    tool_call=tool_call,
                )
            except (ProviderConnectionError, ProviderRateLimitError) as exc:
                self._capture_provider_call(
                    accumulator,
                    started_at=provider_started,
                    success=False,
                    error_type=type(exc).__name__,
                )
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
            self._capture_provider_call(
                accumulator,
                started_at=provider_started,
                success=True,
                error_type=None,
            )

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
                accumulator.repair_attempts = repairs_used
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
                accumulator.repair_attempts = repairs_used
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

    def _capture_provider_call(
        self,
        accumulator: ExecutionAccumulator,
        *,
        started_at: float,
        success: bool,
        error_type: str | None,
    ) -> None:
        metrics = getattr(self._provider, "last_call_metrics", None)
        if not isinstance(metrics, ProviderCallMetrics):
            metrics = ProviderCallMetrics(
                provider_attempts=1,
                latency_ms=round((self._clock() - started_at) * 1000, 3),
                input_tokens=None,
                output_tokens=None,
                total_tokens=None,
                success=success,
                error_type=error_type,
            )
        accumulator.add_call(metrics)

    def _utc_now(self) -> datetime:
        value = self._utc_clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("El reloj UTC debe devolver una fecha con zona.")
        return value.astimezone(UTC)

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
