"""Reglas deterministas de incertidumbre y prioridad de revisión."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from backend.app.schemas import (
    ExecutionMetrics,
    KnowledgeEvidence,
    ReviewPriorityAssessment,
    SimilarityMatch,
    SimilarityResult,
    TriageResult,
    UncertaintyAssessment,
)
from backend.app.services import ReviewPriorityService, UncertaintyService

NOW = datetime(2026, 9, 14, tzinfo=UTC)
PROPOSAL = TriageResult(
    category="riesgo_electrico",
    urgency="alta",
    summary="Cable dañado requiere aislamiento preventivo y una revisión técnica inmediata.",
    department="mantenimiento",
    justification="Regla y evidencia preventiva verificadas por el backend.",
)
EVIDENCE = (
    KnowledgeEvidence(
        source_id="RM-ELEC-001",
        title="Matriz de riesgos PRL",
        section="Regla RM-ELEC-001",
        category="riesgo_electrico",
        excerpt="Aislar la zona y revisar la instalación.",
        source_type="risk_matrix",
        version="1.0.0",
        score=1.0,
    ),
    KnowledgeEvidence(
        source_id="PRL-EL-04",
        title="Procedimiento eléctrico",
        section="Apartado 3.2",
        category="riesgo_electrico",
        excerpt="Comprobar ausencia de tensión antes de intervenir.",
        source_type="preventive_document",
        version="1.0.0",
        score=8.0,
    ),
)
METRICS = ExecutionMetrics(
    provider="local",
    model="modelo-prueba",
    parameters={},
    started_at=NOW,
    completed_at=NOW,
    latency_ms=10,
    provider_attempts=2,
    repair_attempts=0,
    success=True,
    json_valid=True,
    error_type=None,
    evidence=EVIDENCE,
)


def similarity(*, same_location: bool, score: float = 0.8) -> SimilarityResult:
    return SimilarityResult(
        available=True,
        has_similar=True,
        match_count=1,
        matches=(
            SimilarityMatch(
                notice_id=uuid4(),
                score=score,
                same_location=same_location,
                location="Taller" if same_location else "Oficinas",
                created_at=NOW,
                category="riesgo_electrico",
                urgency="alta",
            ),
        ),
    )


def test_clean_execution_has_low_uncertainty_and_is_repeatable():
    service = UncertaintyService()

    first = service.assess(PROPOSAL, METRICS)
    second = service.assess(PROPOSAL, METRICS)

    assert first == second == UncertaintyAssessment(level="low")


def test_one_repair_increases_uncertainty_without_becoming_high():
    result = UncertaintyService().assess(
        PROPOSAL,
        METRICS.model_copy(
            update={"repair_attempts": 1, "provider_attempts": 3}
        ),
    )

    assert result.level == "medium"
    assert result.reasons == ("provider_output_repaired",)


def test_multiple_repairs_make_uncertainty_high():
    result = UncertaintyService().assess(
        PROPOSAL,
        METRICS.model_copy(
            update={"repair_attempts": 2, "provider_attempts": 4}
        ),
    )

    assert result.level == "high"
    assert result.reasons == ("provider_output_repaired", "multiple_repairs")


@pytest.mark.parametrize(
    ("proposal", "metrics", "reason"),
    [
        (PROPOSAL.model_copy(update={"category": "otros"}), METRICS, "generic_category"),
        (PROPOSAL, METRICS.model_copy(update={"evidence": ()}), "incomplete_evidence"),
        (PROPOSAL, METRICS.model_copy(update={"provider_attempts": 3}), "provider_retry"),
    ],
)
def test_each_observable_signal_has_a_closed_reason(proposal, metrics, reason):
    result = UncertaintyService().assess(proposal, metrics)

    assert result.level == "medium"
    assert result.reasons == (reason,)


@pytest.mark.parametrize(
    ("urgency", "expected"),
    [("baja", "low"), ("media", "medium"), ("alta", "high"), ("critica", "critical")],
)
def test_priority_starts_from_risk_urgency(urgency, expected):
    result = ReviewPriorityService().assess(
        urgency,
        UncertaintyAssessment(level="low"),
        SimilarityResult(),
    )

    assert result.level == expected
    assert result.reasons == (f"{expected}_urgency",)


def test_high_uncertainty_can_raise_priority_but_never_create_critical():
    uncertainty = UncertaintyAssessment(
        level="high",
        reasons=("generic_category", "incomplete_evidence"),
    )
    service = ReviewPriorityService()

    assert service.assess("baja", uncertainty, SimilarityResult()).level == "medium"
    assert service.assess("alta", uncertainty, SimilarityResult()).level == "high"
    critical = service.assess("critica", uncertainty, SimilarityResult())
    assert critical.level == "critical"
    assert critical.reasons[0] == "critical_urgency"


def test_same_location_recurrence_raises_more_than_other_location():
    service = ReviewPriorityService()
    uncertainty = UncertaintyAssessment(level="low")

    same = service.assess("media", uncertainty, similarity(same_location=True))
    other = service.assess("media", uncertainty, similarity(same_location=False))

    assert same == ReviewPriorityAssessment(
        level="high",
        reasons=("medium_urgency", "recurrent_same_location"),
    )
    assert other == ReviewPriorityAssessment(
        level="medium",
        reasons=("medium_urgency", "recurrent_risk"),
    )


def test_similarity_score_is_not_interpreted_as_confidence():
    service = ReviewPriorityService()
    uncertainty = UncertaintyAssessment(level="low")

    low_score = service.assess(
        "baja", uncertainty, similarity(same_location=True, score=0.1)
    )
    high_score = service.assess(
        "baja", uncertainty, similarity(same_location=True, score=0.99)
    )

    assert low_score == high_score


def test_two_independent_elevations_stop_at_high():
    result = ReviewPriorityService().assess(
        "baja",
        UncertaintyAssessment(
            level="high",
            reasons=("generic_category", "incomplete_evidence"),
        ),
        similarity(same_location=True),
    )

    assert result.level == "high"
