"""Pruebas transaccionales del repositorio SQLite."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
import sqlite3
from uuid import uuid4

import pytest

from backend.app.repositories import (
    NoticeNotFoundError,
    ReviewConflictError,
    SQLiteNoticeRepository,
)
from backend.app.schemas import (
    ComparisonProviderResult,
    ComparisonRequest,
    ExecutionMetrics,
    ReviewRequest,
    TriageRequest,
    TriageResult,
)

FIXED_TIME = datetime(2026, 9, 10, 10, 30, tzinfo=UTC)
PROPOSAL = TriageResult(
    category="riesgo_electrico",
    urgency="alta",
    summary="Cable deteriorado visible junto al acceso del almacén de demostración.",
    department="mantenimiento",
    justification="Matriz didáctica y propuesta pendiente de revisión profesional.",
)
REQUEST = TriageRequest(
    text="Hay un cable deteriorado.",
    provider="local",
    location="Almacén sintético",
)
METRICS = ExecutionMetrics(
    provider="local",
    model="modelo-prueba",
    parameters={"temperature": 0.0},
    started_at=FIXED_TIME,
    completed_at=FIXED_TIME,
    latency_ms=12.5,
    provider_attempts=2,
    repair_attempts=0,
    input_tokens=20,
    output_tokens=10,
    total_tokens=30,
    success=True,
    json_valid=True,
    error_type=None,
    api_cost=Decimal(0),
    computational_cost=None,
)


@pytest.fixture
def repository(tmp_path):
    return SQLiteNoticeRepository(
        tmp_path / "iaviso-test.db",
        clock=lambda: FIXED_TIME,
    )


def create_proposal(repository):
    return repository.create_triage(
        REQUEST,
        PROPOSAL,
        request_id=str(uuid4()),
        model="modelo-prueba",
        metrics=METRICS,
    )


def review_payload(decision="approved", **changes):
    return ReviewRequest(
        decision=decision,
        reviewer="Técnica de prevención",
        comment="Revisión realizada sobre un caso sintético.",
        expected_version=0,
        **changes,
    )


def test_new_proposal_is_pending_and_preserves_original_data(repository):
    created = create_proposal(repository)
    notices = repository.list_notices()

    assert created.status == "pending_review"
    assert created.version == 0
    assert created.created_at == FIXED_TIME
    assert len(notices) == 1
    notice = notices[0]
    assert notice.text == REQUEST.text
    assert notice.location == REQUEST.location
    assert notice.triage_runs[0].proposal == PROPOSAL
    assert notice.triage_runs[0].metrics == METRICS
    assert notice.triage_runs[0].review is None
    events = repository.list_audit_events(created.notice_id)
    assert [event.event_type for event in events] == ["triage_created"]
    assert events[0].new_status == "pending_review"
    assert events[0].actor is None


def test_modified_review_keeps_original_and_builds_final_classification(repository):
    created = create_proposal(repository)

    reviewed = repository.review_notice(
        created.notice_id,
        review_payload(
            "modified",
            urgency="critica",
            department="seguridad",
        ),
    )

    run = reviewed.triage_run
    assert run.status == "modified"
    assert run.version == 1
    assert run.proposal == PROPOSAL
    assert run.review.final_classification.model_dump() == {
        "category": "riesgo_electrico",
        "urgency": "critica",
        "department": "seguridad",
    }
    assert run.review.reviewer == "Técnica de prevención"
    assert run.review.created_at == FIXED_TIME
    stored_run = repository.list_notices()[0].triage_runs[0]
    assert stored_run == run
    events = repository.list_audit_events(created.notice_id)
    assert [event.new_status for event in events] == ["pending_review", "modified"]


def test_rejected_review_has_no_accepted_final_classification(repository):
    created = create_proposal(repository)

    reviewed = repository.review_notice(
        created.notice_id,
        review_payload("rejected"),
    )

    assert reviewed.triage_run.status == "rejected"
    assert reviewed.triage_run.review.final_classification is None
    assert reviewed.triage_run.proposal == PROPOSAL


def test_duplicate_and_stale_reviews_are_rejected(repository):
    created = create_proposal(repository)
    repository.review_notice(created.notice_id, review_payload())

    with pytest.raises(ReviewConflictError):
        repository.review_notice(created.notice_id, review_payload())


def test_modified_review_must_change_the_effective_classification(repository):
    created = create_proposal(repository)

    with pytest.raises(ReviewConflictError):
        repository.review_notice(
            created.notice_id,
            review_payload("modified", urgency="alta"),
        )


def test_missing_notice_is_controlled(repository):
    with pytest.raises(NoticeNotFoundError):
        repository.review_notice(uuid4(), review_payload())


def test_concurrent_review_allows_exactly_one_winner(tmp_path):
    database_path = tmp_path / "iaviso-concurrent.db"
    repository = SQLiteNoticeRepository(database_path, clock=lambda: FIXED_TIME)
    created = create_proposal(repository)
    reviewers = ("Revisora A", "Revisora B")

    def attempt(reviewer):
        candidate = SQLiteNoticeRepository(database_path, clock=lambda: FIXED_TIME)
        try:
            candidate.review_notice(
                created.notice_id,
                ReviewRequest(
                    decision="approved",
                    reviewer=reviewer,
                    comment="Revisión concurrente sintética.",
                    expected_version=0,
                ),
            )
            return "accepted"
        except ReviewConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(attempt, reviewers))

    assert sorted(outcomes) == ["accepted", "conflict"]
    stored_run = repository.list_notices()[0].triage_runs[0]
    assert stored_run.version == 1
    assert stored_run.status == "approved"
    assert len(repository.list_audit_events(created.notice_id)) == 2


def test_comparison_is_persisted_without_creating_notice(tmp_path):
    database_path = tmp_path / "comparison.db"
    repository = SQLiteNoticeRepository(database_path, clock=lambda: FIXED_TIME)
    request = ComparisonRequest(
        text="Caso único para ambos proveedores.",
        location="Zona sintética",
    )
    external_metrics = METRICS.model_copy(
        update={
            "provider": "external",
            "model": "gemini-prueba",
            "api_cost": None,
        }
    )
    results = (
        ComparisonProviderResult(
            provider="local",
            result=PROPOSAL,
            metrics=METRICS,
        ),
        ComparisonProviderResult(
            provider="external",
            result=PROPOSAL,
            metrics=external_metrics,
        ),
    )

    response = repository.create_comparison(request, results)

    assert response.created_at == FIXED_TIME
    assert repository.list_notices() == ()
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM comparisons").fetchone()[0] == 1
        assert (
            connection.execute("SELECT COUNT(*) FROM comparison_runs").fetchone()[0]
            == 2
        )


def test_phase_six_database_gets_additive_metrics_migration(tmp_path):
    database_path = tmp_path / "phase-six.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE triage_runs (
                id TEXT PRIMARY KEY,
                notice_id TEXT NOT NULL,
                request_id TEXT NOT NULL UNIQUE,
                provider TEXT NOT NULL,
                model TEXT,
                status TEXT NOT NULL,
                version INTEGER NOT NULL,
                proposal_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

    SQLiteNoticeRepository(database_path)

    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(triage_runs)")
        }
    assert "metrics_json" in columns
