"""Contratos auditables de telemetría, costes y comparación."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from .catalogs import Category, Department, Provider, Urgency
from .errors import ErrorCode
from .knowledge import KnowledgeEvidence
from .privacy import PrivacyMetadata
from .review_policy import UncertaintyLevel
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
    evidence: tuple[KnowledgeEvidence, ...] = ()


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


ComparisonReviewer = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]
ComparisonComment = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2000),
]


class ComparisonReviewRequest(MetricsContract):
    """Clasificación de referencia decidida por una persona."""

    category: Category
    urgency: Urgency
    department: Department
    reviewer: ComparisonReviewer
    comment: ComparisonComment


class ComparisonReviewRecord(ComparisonReviewRequest):
    id: UUID
    comparison_id: UUID
    created_at: datetime


class ComparisonResponse(MetricsContract):
    comparison_id: UUID
    created_at: datetime
    results: tuple[ComparisonProviderResult, ...]
    review: ComparisonReviewRecord | None = None
    privacy: PrivacyMetadata = PrivacyMetadata()

    @model_validator(mode="after")
    def require_both_providers(self):
        if (
            len(self.results) != 2
            or {item.provider for item in self.results} != {"local", "external"}
        ):
            raise ValueError("La comparación debe incluir local y external una vez.")
        return self


class ProviderMetricsSummary(MetricsContract):
    provider: Provider
    models: tuple[str, ...]
    runs: int = Field(strict=True, ge=0)
    reviewed_runs: int = Field(strict=True, ge=0)
    mean_latency_ms: float | None = Field(default=None, ge=0)
    mean_provider_attempts: float | None = Field(default=None, ge=0)
    repair_rate: float | None = Field(default=None, ge=0, le=1)
    mean_repair_attempts: float | None = Field(default=None, ge=0)
    success_rate: float | None = Field(default=None, ge=0, le=1)
    json_valid_rate: float | None = Field(default=None, ge=0, le=1)
    json_valid_observations: int = Field(strict=True, ge=0)
    human_agreement_rate: float | None = Field(default=None, ge=0, le=1)
    mean_total_tokens: float | None = Field(default=None, ge=0)
    token_observations: int = Field(strict=True, ge=0)
    mean_api_cost: Decimal | None = Field(default=None, ge=0)
    api_cost_currency: str | None = None
    cost_observations: int = Field(strict=True, ge=0)
    temperatures: tuple[float, ...]
    top_p_values: tuple[float, ...]


class UncertaintyLevelSummary(MetricsContract):
    """Distribución operativa y corrección humana para un nivel técnico."""

    level: UncertaintyLevel
    runs: int = Field(strict=True, ge=0)
    rate: float | None = Field(default=None, ge=0, le=1)
    reviewed_runs: int = Field(strict=True, ge=0)
    human_correction_rate: float | None = Field(default=None, ge=0, le=1)


class MetricsSummary(MetricsContract):
    total_notices: int = Field(strict=True, ge=0)
    total_runs: int = Field(strict=True, ge=0)
    pending_review: int = Field(strict=True, ge=0)
    reviewed: int = Field(strict=True, ge=0)
    approved: int = Field(strict=True, ge=0)
    modified: int = Field(strict=True, ge=0)
    rejected: int = Field(strict=True, ge=0)
    acceptance_rate: float | None = Field(default=None, ge=0, le=1)
    correction_rate: float | None = Field(default=None, ge=0, le=1)
    rejection_rate: float | None = Field(default=None, ge=0, le=1)
    review_policy_observations: int = Field(strict=True, ge=0)
    pending_high_priority: int = Field(strict=True, ge=0)
    pending_critical_priority: int = Field(strict=True, ge=0)
    uncertainty: tuple[UncertaintyLevelSummary, ...]
    providers: tuple[ProviderMetricsSummary, ...]

    @model_validator(mode="after")
    def require_both_providers(self):
        if (
            len(self.providers) != 2
            or {item.provider for item in self.providers} != {"local", "external"}
        ):
            raise ValueError("El resumen debe incluir local y external una vez.")
        if (
            len(self.uncertainty) != 3
            or {item.level for item in self.uncertainty} != {"low", "medium", "high"}
        ):
            raise ValueError("El resumen debe incluir los tres niveles de incertidumbre.")
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
