"""Pruebas del panorama preventivo sin base de datos ni proveedores."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from backend.app.schemas import (
    ClassificationDecision,
    NoticeRecord,
    ReviewPriorityAssessment,
    ReviewRecord,
    TriageResult,
    TriageRunRecord,
)
from backend.app.services import PreventiveAnalyticsService
from backend.app.services.location_normalization import normalize_location

NOW = datetime(2026, 9, 14, 12, tzinfo=UTC)
SUMMARY = "Aviso preventivo válido pendiente siempre de revisión por personal técnico"


def notice(
    identifier: int,
    *,
    age_days: int = 1,
    location: str | None = "Almacén",
    status="approved",
    proposal_category="riesgo_electrico",
    proposal_urgency="media",
    final_category=None,
    final_urgency=None,
    priority="medium",
) -> NoticeRecord:
    created_at = NOW - timedelta(days=age_days)
    proposal = TriageResult(
        category=proposal_category,
        urgency=proposal_urgency,
        department="prevencion",
        summary=SUMMARY,
        justification="Clasificación sintética destinada exclusivamente a pruebas.",
    )
    review = None
    if status != "pending_review":
        final = None
        if status != "rejected":
            final = ClassificationDecision(
                category=final_category or proposal_category,
                urgency=final_urgency or proposal_urgency,
                department="prevencion",
            )
        review = ReviewRecord(
            id=UUID(int=10_000 + identifier),
            decision=status,
            final_classification=final,
            comment="Revisión humana sintética para pruebas.",
            reviewer="Técnica de pruebas",
            created_at=created_at + timedelta(hours=1),
        )
    priority_reason = {
        "low": "low_urgency",
        "medium": "medium_urgency",
        "high": "high_urgency",
        "critical": "critical_urgency",
    }[priority]
    run = TriageRunRecord(
        id=UUID(int=1_000 + identifier),
        request_id=f"request-{identifier}",
        provider="local",
        model="test",
        status=status,
        version=1 if review else 0,
        proposal=proposal,
        created_at=created_at,
        metrics=None,
        review_priority=ReviewPriorityAssessment(
            level=priority,
            reasons=(priority_reason,),
        ),
        review_policy_version="v1",
        review=review,
    )
    return NoticeRecord(
        id=UUID(int=identifier),
        text=f"Aviso sintético {identifier}",
        location=location,
        created_at=created_at,
        triage_runs=(run,),
    )


def service() -> PreventiveAnalyticsService:
    return PreventiveAnalyticsService(clock=lambda: NOW)


@pytest.mark.parametrize(
    "value",
    ["Almacén", "almacén", " ALMACÉN ", "Almace\u0301n"],
)
def test_location_normalization_is_shared_and_deterministic(value):
    assert normalize_location(value) == "almacén"


def test_blank_location_uses_the_explicit_missing_group():
    result = service().summarize((notice(1, location="   "),), "30")

    assert result.by_location[0].location == "Sin ubicación"


def test_location_normalization_does_not_merge_distinct_zone_names():
    result = service().summarize(
        (notice(1, location="Almacén"), notice(2, location="Almacén norte")),
        "30",
    )

    assert {item.location for item in result.by_location} == {
        "Almacén",
        "Almacén norte",
    }


def test_only_human_confirmed_classification_feeds_preventive_rankings():
    result = service().summarize(
        (
            notice(1, final_category="maquinaria", final_urgency="alta"),
            notice(
                2,
                status="modified",
                proposal_category="otros",
                final_category="caidas_obstaculos",
                final_urgency="critica",
            ),
            notice(3, status="rejected", proposal_category="incendio"),
            notice(4, status="pending_review", proposal_category="ergonomia"),
        ),
        "30",
    )

    assert result.totals.confirmed_notices == 2
    assert result.totals.pending_notices == 1
    assert result.totals.rejected_notices == 1
    assert [(item.category, item.total) for item in result.by_category] == [
        ("caidas_obstaculos", 1),
        ("maquinaria", 1),
    ]
    assert {item.urgency: item.total for item in result.by_urgency} == {
        "alta": 1,
        "critica": 1,
    }
    assert result.pending_by_priority.levels[1].total == 1


def test_locations_hotspots_missing_location_and_stable_ranking():
    data = (
        notice(1, location="Almacén", final_category="caidas_obstaculos"),
        notice(
            2,
            location=" ALMACÉN ",
            final_category="caidas_obstaculos",
            final_urgency="alta",
        ),
        notice(3, location="Taller", final_category="maquinaria"),
        notice(4, location=None, final_category="ergonomia"),
    )

    first = service().summarize(data, "30")
    second = service().summarize(tuple(reversed(data)), "30")

    assert first == second
    assert [(item.location, item.total) for item in first.by_location] == [
        ("Almacén", 2),
        ("Sin ubicación", 1),
        ("Taller", 1),
    ]
    assert first.by_location[0].high_or_critical_urgency == 1
    assert len(first.location_category_hotspots) == 1
    assert first.location_category_hotspots[0].location == "Almacén"
    assert first.location_category_hotspots[0].total == 2
    assert first.hotspot_minimum == 2


@pytest.mark.parametrize(
    ("window", "expected", "granularity"),
    [
        ("7", 1, "day"),
        ("30", 2, "day"),
        ("90", 3, "week"),
        ("all", 4, "month"),
    ],
)
def test_supported_windows_exclude_old_data(window, expected, granularity):
    result = service().summarize(
        (
            notice(1, age_days=6),
            notice(2, age_days=20),
            notice(3, age_days=60),
            notice(4, age_days=120),
        ),
        window,
    )

    assert result.totals.confirmed_notices == expected
    assert result.period.granularity == granularity
    assert sum(point.total_notices for point in result.timeline) == expected


def test_pending_priority_is_operational_and_separate_from_urgency():
    result = service().summarize(
        (
            notice(1, status="pending_review", priority="critical"),
            notice(2, status="pending_review", priority="high"),
            notice(3, final_urgency="baja"),
        ),
        "30",
    )

    pending = {item.level: item.total for item in result.pending_by_priority.levels}
    assert pending == {"low": 0, "medium": 0, "high": 1, "critical": 1}
    assert [(item.urgency, item.total) for item in result.by_urgency] == [("baja", 1)]


def test_empty_and_small_datasets_do_not_claim_a_trend():
    empty = service().summarize((), "30")
    small = service().summarize((notice(1), notice(2)), "30")

    assert empty.totals.confirmed_notices == 0
    assert empty.timeline == ()
    assert empty.enough_data_for_trends is False
    assert small.enough_data_for_trends is False
    assert service().summarize((notice(1), notice(2), notice(3)), "30").enough_data_for_trends is True
