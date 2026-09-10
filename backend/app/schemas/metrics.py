"""Contratos auditables de telemetría, costes y comparación."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, model_validator

from .catalogs import Category, Department, Provider, Urgency
from .errors import ErrorCode
from .triage import LocationText, NoticeText, TriageResult


class MetricsContract(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class PricingReference(MetricsContract):
    """Tarifa externa reproducible; nunca se aplica a otro modelo."""

    model: str
    currency: str
    input_per_million_tokens: Decimal = Field(ge=0)
    output_per_million_tokens: Decimal = Field(ge=0)
    source: AnyHttpUrl
    checked_on: date


class ExecutionMetrics(MetricsContract):
    """Métricas de una ejecución; None significa dato no observado."""

    provider: Provider
    model: str | None
    parameters: dict[str, int | float]
    started_at: datetime
    completed_at: datetime
    latency_ms: float = Field(ge=0)
    provider_attempts: int = Field(strict=True, ge=0)
    repair_attempts: int = Field(strict=True, ge=0)
    input_tokens: int | None = Field(default=None, strict=True, ge=0)
    output_tokens: int | None = Field(default=None, strict=True, ge=0)
    total_tokens: int | None = Field(default=None, strict=True, ge=0)
    success: bool
    json_valid: bool | None
    error_type: str | None
    api_cost: Decimal | None = Field(default=None, ge=0)
    api_cost_currency: str | None = None
    computational_cost: Decimal | None = Field(default=None, ge=0)
    pricing: PricingReference | None = None


class ComparisonRequest(MetricsContract):
    """Un único aviso que se ejecuta contra ambos proveedores."""

    text: NoticeText
    location: LocationText | None = None


class ComparisonProviderResult(MetricsContract):
    provider: Provider
    result: TriageResult | None
    error_code: ErrorCode | None = None
    metrics: ExecutionMetrics

    @model_validator(mode="after")
    def providers_must_match(self):
        if self.provider != self.metrics.provider:
            raise ValueError("El proveedor del resultado y sus métricas no coincide.")
        if self.metrics.success != (self.result is not None):
            raise ValueError("El éxito medido debe coincidir con la presencia de resultado.")
        if (self.result is None) != (self.error_code is not None):
            raise ValueError("Un fallo comparativo debe incluir un código de error.")
        return self


class ComparisonResponse(MetricsContract):
    comparison_id: UUID
    created_at: datetime
    results: tuple[ComparisonProviderResult, ...]

    @model_validator(mode="after")
    def require_both_providers(self):
        if (
            len(self.results) != 2
            or {item.provider for item in self.results} != {"local", "external"}
        ):
            raise ValueError("La comparación debe incluir local y external una vez.")
        return self


class EvaluationCase(MetricsContract):
    id: str
    text: NoticeText
    location: LocationText | None = None
    expected_category: Category
    expected_urgency: Urgency
    expected_department: Department
    tags: tuple[str, ...] = ()
    bias_pair_id: str | None = None
    bias_attribute: str | None = None

    @model_validator(mode="after")
    def complete_bias_pair_metadata(self):
        if (self.bias_pair_id is None) != (self.bias_attribute is None):
            raise ValueError("Un par de sesgo debe declarar id y atributo.")
        return self


class EvaluationDataset(MetricsContract):
    version: str
    disclaimer: str
    cases: tuple[EvaluationCase, ...]

    @model_validator(mode="after")
    def require_unique_cases(self):
        identifiers = [case.id for case in self.cases]
        if not identifiers or len(identifiers) != len(set(identifiers)):
            raise ValueError("El dataset debe contener casos con identificadores únicos.")
        return self


class EvaluationObservation(MetricsContract):
    case_id: str
    provider: Provider
    result: TriageResult | None
    metrics: ExecutionMetrics
    review_decision: Literal["approved", "modified", "rejected"] | None = None


class ProviderEvaluationSummary(MetricsContract):
    provider: Provider
    cases: int = Field(strict=True, ge=0)
    category_accuracy: float | None = Field(default=None, ge=0, le=1)
    urgency_accuracy: float | None = Field(default=None, ge=0, le=1)
    department_accuracy: float | None = Field(default=None, ge=0, le=1)
    json_valid_rate: float | None = Field(default=None, ge=0, le=1)
    mean_latency_ms: float | None = Field(default=None, ge=0)
    mean_api_cost: Decimal | None = Field(default=None, ge=0)
    api_cost_currency: str | None = None
    reviewed_notices: int = Field(strict=True, ge=0)
    human_correction_rate: float | None = Field(default=None, ge=0, le=1)


class EvaluationReport(MetricsContract):
    dataset_version: str
    generated_at: datetime
    disclaimer: str
    summaries: tuple[ProviderEvaluationSummary, ...]
