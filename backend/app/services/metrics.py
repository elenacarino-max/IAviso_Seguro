"""Conversión determinista de telemetría interna a métricas persistibles."""

from decimal import Decimal

from backend.app.core.settings import Settings
from backend.app.providers import ProviderConnectionError, ProviderRateLimitError
from backend.app.schemas import (
    ErrorCode,
    ExecutionMetrics,
    PricingReference,
    TriageRequest,
)
from backend.app.tools import (
    InvalidRiskMatrixError,
    InvalidToolArgumentsError,
    RequiredToolCallError,
    ToolStepLimitError,
)

from .errors import InvalidProviderOutputError
from .execution import ExecutionTelemetry

_MILLION = Decimal(1_000_000)


class MetricsService:
    """Añade configuración y coste sin inventar métricas no observadas."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(
        self,
        request: TriageRequest,
        telemetry: ExecutionTelemetry,
    ) -> ExecutionMetrics:
        model = self.model_for(request.provider)
        pricing = self._pricing_for(request.provider, model)
        api_cost = self._api_cost(telemetry, pricing, request.provider)
        return ExecutionMetrics(
            provider=request.provider,
            model=model,
            parameters=self._parameters_for(request.provider),
            started_at=telemetry.started_at,
            completed_at=telemetry.completed_at,
            latency_ms=telemetry.latency_ms,
            provider_attempts=telemetry.provider_attempts,
            repair_attempts=telemetry.repair_attempts,
            input_tokens=telemetry.input_tokens,
            output_tokens=telemetry.output_tokens,
            total_tokens=telemetry.total_tokens,
            success=telemetry.success,
            json_valid=telemetry.json_valid,
            error_type=telemetry.error_type,
            api_cost=api_cost,
            api_cost_currency=(pricing.currency if pricing is not None else None),
            computational_cost=None,
            pricing=pricing,
        )

    def model_for(self, provider: str) -> str | None:
        if provider == "local":
            return self._settings.local_model or None
        return self._settings.external_model or None

    def _parameters_for(self, provider: str) -> dict[str, int | float]:
        temperature = (
            self._settings.ollama_temperature
            if provider == "local"
            else self._settings.external_temperature
        )
        top_p = (
            self._settings.ollama_top_p
            if provider == "local"
            else self._settings.external_top_p
        )
        values: dict[str, int | float] = {
            "temperature": temperature,
            "top_p": top_p,
            "timeout_seconds": self._settings.llm_timeout_seconds,
            "max_repair_attempts": self._settings.llm_repair_attempts,
        }
        if provider == "external":
            values["max_retries"] = self._settings.llm_max_retries
        return values

    def _pricing_for(
        self,
        provider: str,
        model: str | None,
    ) -> PricingReference | None:
        if provider != "external" or model != self._settings.external_price_model:
            return None
        return PricingReference(
            model=self._settings.external_price_model,
            currency=self._settings.external_price_currency,
            input_per_million_tokens=self._settings.external_input_price_per_million,
            output_per_million_tokens=self._settings.external_output_price_per_million,
            source=self._settings.external_price_source,
            checked_on=self._settings.external_price_checked_on,
        )

    @staticmethod
    def _api_cost(
        telemetry: ExecutionTelemetry,
        pricing: PricingReference | None,
        provider: str,
    ) -> Decimal | None:
        if provider == "local":
            return Decimal(0)
        if (
            pricing is None
            or telemetry.input_tokens is None
            or telemetry.output_tokens is None
        ):
            return None
        return (
            Decimal(telemetry.input_tokens) * pricing.input_per_million_tokens
            + Decimal(telemetry.output_tokens) * pricing.output_per_million_tokens
        ) / _MILLION


def error_code_for(error: Exception | None) -> ErrorCode | None:
    """Traduce un fallo controlado al mismo código estable que usa HTTP."""

    mappings: tuple[tuple[type[Exception], ErrorCode], ...] = (
        (InvalidProviderOutputError, "invalid_provider_output"),
        (ProviderConnectionError, "provider_unavailable"),
        (ProviderRateLimitError, "provider_rate_limited"),
        (InvalidToolArgumentsError, "invalid_tool_arguments"),
        (InvalidRiskMatrixError, "invalid_risk_matrix"),
        (RequiredToolCallError, "required_tool_not_executed"),
        (ToolStepLimitError, "tool_step_limit_exceeded"),
    )
    for error_type, code in mappings:
        if isinstance(error, error_type):
            return code
    return None
