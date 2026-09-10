"""Pruebas de coste explícito y evaluación reproducible."""

from datetime import UTC, datetime
from decimal import Decimal

from backend.app.core.settings import Settings
from backend.app.schemas import EvaluationObservation, TriageRequest, TriageResult
from backend.app.providers import MockTriageProvider
from backend.app.services import (
    EvaluationService,
    ExecutionTelemetry,
    MetricsService,
    TriageService,
    load_evaluation_dataset,
)

NOW = datetime(2026, 9, 10, 12, tzinfo=UTC)
RESULT = TriageResult(
    category="riesgo_electrico",
    urgency="alta",
    summary="Cable deteriorado visible junto al acceso del almacén de demostración.",
    department="mantenimiento",
    justification="Resultado sintético pendiente de revisión preventiva profesional.",
)


def telemetry(*, input_tokens=100, output_tokens=40):
    return ExecutionTelemetry(
        started_at=NOW,
        completed_at=NOW,
        latency_ms=20,
        provider_attempts=2,
        repair_attempts=1,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=(
            input_tokens + output_tokens
            if input_tokens is not None and output_tokens is not None
            else None
        ),
        success=True,
        json_valid=True,
        error_type=None,
    )


def test_external_cost_uses_matching_dated_tariff():
    settings = Settings(_env_file=None)
    metrics = MetricsService(settings).build(
        TriageRequest(text="Caso sintético", provider="external"),
        telemetry(),
    )

    assert metrics.api_cost == Decimal("0.00013")
    assert metrics.api_cost_currency == "USD"
    assert metrics.pricing.checked_on.isoformat() == "2026-09-10"


def test_unknown_tokens_or_tariff_remain_unknown():
    settings = Settings(_env_file=None, external_model="otro-modelo")
    metrics = MetricsService(settings).build(
        TriageRequest(text="Caso sintético", provider="external"),
        telemetry(input_tokens=None),
    )

    assert metrics.api_cost is None
    assert metrics.pricing is None


def test_local_api_cost_is_zero_but_computational_cost_is_unknown():
    metrics = MetricsService(Settings(_env_file=None)).build(
        TriageRequest(text="Caso sintético", provider="local"),
        telemetry(input_tokens=None, output_tokens=None),
    )

    assert metrics.api_cost == 0
    assert metrics.computational_cost is None


def test_dataset_covers_catalog_ambiguity_and_insufficient_information():
    dataset = load_evaluation_dataset("data/evaluation/avisos.v1.json")

    assert len({case.expected_category for case in dataset.cases}) == 9
    tags = {tag for case in dataset.cases for tag in case.tags}
    assert {"ambiguous", "insufficient_information"} <= tags


def test_bias_pairs_only_change_irrelevant_age_and_keep_expected_outcome():
    dataset = load_evaluation_dataset("data/evaluation/avisos.v1.json")
    pairs = {}
    for case in dataset.cases:
        if case.bias_pair_id is not None:
            pairs.setdefault(case.bias_pair_id, []).append(case)

    assert len(pairs) >= 2
    for variants in pairs.values():
        assert len(variants) == 2
        first, second = variants
        assert first.bias_attribute == second.bias_attribute == "edad"
        assert (
            first.expected_category,
            first.expected_urgency,
            first.expected_department,
        ) == (
            second.expected_category,
            second.expected_urgency,
            second.expected_department,
        )
        different_tokens = [
            (left, right)
            for left, right in zip(first.text.split(), second.text.split(), strict=True)
            if left != right
        ]
        assert len(different_tokens) == 1


def test_human_correction_rate_uses_only_reviewed_notices():
    dataset = load_evaluation_dataset("data/evaluation/avisos.v1.json")
    metrics = MetricsService(
        Settings(_env_file=None, local_model="modelo-prueba")
    ).build(
        TriageRequest(text="Caso sintético", provider="local"),
        telemetry(),
    )
    observations = (
        EvaluationObservation(
            case_id="elec-001",
            provider="local",
            result=RESULT,
            metrics=metrics,
            review_decision="modified",
        ),
        EvaluationObservation(
            case_id="caida-001",
            provider="local",
            result=RESULT,
            metrics=metrics,
            review_decision="approved",
        ),
        EvaluationObservation(
            case_id="incendio-001",
            provider="local",
            result=RESULT,
            metrics=metrics,
        ),
    )

    report = EvaluationService(clock=lambda: NOW).summarize(dataset, observations)
    local = report.summaries[0]
    assert local.reviewed_notices == 2
    assert local.human_correction_rate == 0.5
    assert local.mean_latency_ms == 20
    assert local.mean_api_cost == 0


def test_evaluation_runner_executes_each_case_with_both_providers():
    complete = load_evaluation_dataset("data/evaluation/avisos.v1.json")
    dataset = complete.model_copy(update={"cases": (complete.cases[-1],)})
    service = EvaluationService(clock=lambda: NOW)

    report = service.run(
        dataset,
        TriageService(MockTriageProvider()),
        MetricsService(Settings(_env_file=None)),
    )

    assert [summary.provider for summary in report.summaries] == [
        "local",
        "external",
    ]
    assert [summary.cases for summary in report.summaries] == [1, 1]
