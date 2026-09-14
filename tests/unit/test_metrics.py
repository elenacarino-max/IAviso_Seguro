"""Pruebas de coste explícito y evaluación reproducible."""

import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest

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
AUTO_JSON_VALID = object()
RESULT = TriageResult(
    category="riesgo_electrico",
    urgency="alta",
    summary="Cable deteriorado visible junto al acceso del almacén de demostración.",
    department="mantenimiento",
    justification="Resultado sintético pendiente de revisión preventiva profesional.",
)


def telemetry(
    *,
    input_tokens=100,
    output_tokens=40,
    latency_ms=20,
    success=True,
    json_valid=True,
    error_type=None,
):
    return ExecutionTelemetry(
        started_at=NOW,
        completed_at=NOW,
        latency_ms=latency_ms,
        provider_attempts=2,
        repair_attempts=1,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=(
            input_tokens + output_tokens
            if input_tokens is not None and output_tokens is not None
            else None
        ),
        success=success,
        json_valid=json_valid,
        error_type=error_type,
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


def test_execution_evidence_is_preserved_in_persistible_metrics():
    request = TriageRequest(text="Caso sintético", provider="local")
    execution = TriageService(MockTriageProvider()).execute(
        request,
        request_id="metrics-evidence",
    )

    metrics = MetricsService(Settings(_env_file=None)).build(
        request,
        execution.telemetry,
        evidence=execution.evidence,
    )

    assert metrics.evidence[0].source_type == "risk_matrix"
    assert metrics.evidence[0].source_id == "RM-OTRO-001"
    assert metrics.evidence[1].source_id == "GUIA-OBS-01"


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


def evaluation_result(case, *, correct=True):
    category = case.expected_category
    urgency = case.expected_urgency
    department = case.expected_department
    if not correct:
        category = "otros" if category != "otros" else "incendio"
        urgency = "baja" if urgency != "baja" else "critica"
        department = "limpieza" if department != "limpieza" else "seguridad"
    return TriageResult(
        category=category,
        urgency=urgency,
        summary="Resultado sintético válido para evaluación controlada sin coincidencias esperadas adicionales.",
        department=department,
        justification="Resultado sintético destinado únicamente a comprobar el benchmark.",
    )


def evaluation_observation(
    case,
    provider,
    *,
    result,
    error_type=None,
    json_valid=AUTO_JSON_VALID,
    latency_ms=20,
):
    request = TriageRequest(
        text=case.text,
        location=case.location,
        provider=provider,
    )
    metrics = MetricsService(Settings(_env_file=None)).build(
        request,
        telemetry(
            input_tokens=100 if result is not None else None,
            output_tokens=40 if result is not None else None,
            latency_ms=latency_ms,
            success=result is not None,
            json_valid=(
                result is not None
                if json_valid is AUTO_JSON_VALID
                else json_valid
            ),
            error_type=error_type,
        ),
    )
    return EvaluationObservation(
        case_id=case.id,
        provider=provider,
        result=result,
        metrics=metrics,
    )


def test_quality_uses_all_evaluable_cases_and_preserves_real_zero():
    complete = load_evaluation_dataset("data/evaluation/avisos.v1.json")
    dataset = complete.model_copy(update={"cases": complete.cases[:2]})
    correct = [
        evaluation_observation(
            case,
            "local",
            result=evaluation_result(case),
        )
        for case in dataset.cases
    ]
    wrong = [
        evaluation_observation(
            case,
            "external",
            result=evaluation_result(case, correct=False),
        )
        for case in dataset.cases
    ]

    report = EvaluationService(clock=lambda: NOW).summarize(
        dataset,
        (*correct, *wrong),
    )
    local, external = report.summaries

    assert local.category_accuracy == 1
    assert local.evaluated_cases == local.cases == 2
    assert local.failed_cases == 0
    assert external.category_accuracy == 0.0
    assert external.urgency_accuracy == 0.0
    assert external.department_accuracy == 0.0
    assert external.evaluated_cases == external.cases == 2
    assert external.failed_cases == 0


def test_partial_quality_uses_only_evaluable_results():
    complete = load_evaluation_dataset("data/evaluation/avisos.v1.json")
    dataset = complete.model_copy(update={"cases": complete.cases[:3]})
    observations = (
        evaluation_observation(
            dataset.cases[0],
            "local",
            result=evaluation_result(dataset.cases[0]),
            latency_ms=10,
        ),
        evaluation_observation(
            dataset.cases[1],
            "local",
            result=evaluation_result(dataset.cases[1], correct=False),
            latency_ms=30,
        ),
        evaluation_observation(
            dataset.cases[2],
            "local",
            result=None,
            error_type="provider_unavailable",
            latency_ms=500,
        ),
    )

    local = EvaluationService(clock=lambda: NOW).summarize(
        dataset,
        observations,
    ).summaries[0]

    assert local.cases == 3
    assert local.evaluated_cases == 2
    assert local.failed_cases == 1
    assert local.category_accuracy == 0.5
    assert local.urgency_accuracy == 0.5
    assert local.department_accuracy == 0.5
    assert local.mean_latency_ms == 20


@pytest.mark.parametrize(
    ("error_type", "json_valid"),
    [
        pytest.param("provider_unavailable", None, id="connection"),
        pytest.param("provider_unavailable", None, id="timeout"),
        pytest.param("provider_rate_limited", None, id="rate-limit"),
        pytest.param("invalid_provider_output", False, id="invalid-output"),
    ],
)
def test_unavailable_provider_has_no_false_quality_or_execution_metrics(
    error_type,
    json_valid,
):
    complete = load_evaluation_dataset("data/evaluation/avisos.v1.json")
    dataset = complete.model_copy(update={"cases": complete.cases[:2]})
    observations = tuple(
        evaluation_observation(
            case,
            "external",
            result=None,
            error_type=error_type,
            json_valid=json_valid,
        )
        for case in dataset.cases
    )

    external = EvaluationService(clock=lambda: NOW).summarize(
        dataset,
        observations,
    ).summaries[1]

    assert external.cases == 2
    assert external.evaluated_cases == 0
    assert external.failed_cases == 2
    assert external.category_accuracy is None
    assert external.urgency_accuracy is None
    assert external.department_accuracy is None
    assert external.mean_latency_ms is None
    assert external.mean_api_cost is None
    assert external.json_valid_rate == (0.0 if json_valid is False else None)


def test_healthy_provider_keeps_metrics_when_other_provider_is_unavailable():
    complete = load_evaluation_dataset("data/evaluation/avisos.v1.json")
    dataset = complete.model_copy(update={"cases": complete.cases[:2]})
    observations = []
    for case in dataset.cases:
        observations.append(
            evaluation_observation(
                case,
                "local",
                result=evaluation_result(case),
                latency_ms=15,
            )
        )
        observations.append(
            evaluation_observation(
                case,
                "external",
                result=None,
                error_type="provider_unavailable",
            )
        )

    report = EvaluationService(clock=lambda: NOW).summarize(dataset, observations)
    local, external = report.summaries

    assert local.category_accuracy == 1
    assert local.mean_latency_ms == 15
    assert local.mean_api_cost == 0
    assert external.category_accuracy is None
    assert external.mean_latency_ms is None


def test_evaluation_report_contains_no_nan_or_infinity():
    complete = load_evaluation_dataset("data/evaluation/avisos.v1.json")
    dataset = complete.model_copy(update={"cases": complete.cases[:1]})
    observation = evaluation_observation(
        dataset.cases[0],
        "local",
        result=None,
        error_type="provider_unavailable",
    )

    report = EvaluationService(clock=lambda: NOW).summarize(dataset, (observation,))

    json.dumps(report.model_dump(mode="json"), allow_nan=False)


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
    assert [summary.evaluated_cases for summary in report.summaries] == [1, 1]
    assert [summary.failed_cases for summary in report.summaries] == [0, 0]
