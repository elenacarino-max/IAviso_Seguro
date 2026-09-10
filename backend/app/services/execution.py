"""Resultado medido de una ejecución completa de triaje."""

from dataclasses import dataclass, field
from datetime import datetime

from backend.app.providers import ProviderCallMetrics
from backend.app.schemas import TriageResult


@dataclass(frozen=True, slots=True)
class ExecutionTelemetry:
    started_at: datetime
    completed_at: datetime
    latency_ms: float
    provider_attempts: int
    repair_attempts: int
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    success: bool
    json_valid: bool | None
    error_type: str | None


@dataclass(frozen=True, slots=True)
class TriageExecution:
    result: TriageResult | None
    telemetry: ExecutionTelemetry
    error: Exception | None = field(default=None, repr=False, compare=False)


class ExecutionAccumulator:
    def __init__(self, *, started_at: datetime, started_tick: float) -> None:
        self.started_at = started_at
        self.started_tick = started_tick
        self.provider_attempts = 0
        self.repair_attempts = 0
        self._input_tokens: list[int | None] = []
        self._output_tokens: list[int | None] = []
        self._total_tokens: list[int | None] = []

    def add_call(self, metrics: ProviderCallMetrics) -> None:
        self.provider_attempts += metrics.provider_attempts
        self._input_tokens.append(metrics.input_tokens)
        self._output_tokens.append(metrics.output_tokens)
        self._total_tokens.append(metrics.total_tokens)

    def finish(
        self,
        *,
        completed_at: datetime,
        completed_tick: float,
        success: bool,
        error_type: str | None,
        json_valid: bool | None = None,
    ) -> ExecutionTelemetry:
        return ExecutionTelemetry(
            started_at=self.started_at,
            completed_at=completed_at,
            latency_ms=round((completed_tick - self.started_tick) * 1000, 3),
            provider_attempts=self.provider_attempts,
            repair_attempts=self.repair_attempts,
            input_tokens=self._complete_sum(self._input_tokens),
            output_tokens=self._complete_sum(self._output_tokens),
            total_tokens=self._complete_sum(self._total_tokens),
            success=success,
            json_valid=True if success else json_valid,
            error_type=error_type,
        )

    @staticmethod
    def _complete_sum(values: list[int | None]) -> int | None:
        if not values or any(value is None for value in values):
            return None
        return sum(value for value in values if value is not None)
