"""Pruebas del recorrido HTTP de triaje con herramienta real."""

import pytest
from fastapi.testclient import TestClient

from backend.app.api.routes_triage import get_notice_repository, get_triage_service
from backend.app.main import app
from backend.app.providers import MockTriageProvider
from backend.app.repositories import SQLiteNoticeRepository
from backend.app.services import TriageService

client = TestClient(app)


@pytest.fixture(autouse=True)
def use_mock_provider_for_contract_tests(tmp_path):
    repository = SQLiteNoticeRepository(tmp_path / "api-test.db")
    app.dependency_overrides[get_triage_service] = lambda: TriageService(
        MockTriageProvider()
    )
    app.dependency_overrides[get_notice_repository] = lambda: repository
    try:
        yield repository
    finally:
        app.dependency_overrides.clear()


def test_health_reports_service_available():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_risk_matrix_endpoint_exposes_the_validated_catalog():
    response = client.get("/api/v1/risk-matrix")

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == "1.0.0"
    assert len(body["rules"]) == 9
    assert {item["category"] for item in body["rules"]} == {
        "riesgo_electrico",
        "caidas_obstaculos",
        "incendio",
        "maquinaria",
        "sustancias_peligrosas",
        "problemas_estructurales",
        "falta_epi",
        "ergonomia",
        "otros",
    }
    assert "no es normativa" in body["disclaimer"].lower()


@pytest.mark.parametrize("provider", ["local", "external"])
def test_triage_contract_accepts_both_provider_names_with_injected_mock(provider):
    response = client.post(
        "/api/v1/triage",
        json={
            "text": "Hay agua derramada en el pasillo.",
            "provider": provider,
            "location": "Almacén de demostración",
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "pending_review"
    assert result["version"] == 0
    assert result["provider"] == provider
    assert result["notice_id"]
    assert result["triage_run_id"]
    assert result["metrics"]["provider"] == provider
    assert result["metrics"]["provider_attempts"] == 2
    assert result["metrics"]["computational_cost"] is None
    assert result["category"] == "otros"
    assert result["urgency"] == "media"
    assert result["department"] == "prevencion"
    assert result["summary"] == (
        "Aviso recibido correctamente y preparado para revisión humana del técnico."
    )
    assert "Matriz didáctica 1.0.0, regla RM-OTRO-001" in result["justification"]
    assert "revisión profesional" in result["justification"]


@pytest.mark.parametrize(
    "payload",
    [
        {"text": "", "provider": "local"},
        {"text": "Aviso sintético", "provider": "desconocido"},
        {"text": "Aviso sintético"},
        {"text": "Aviso sintético", "provider": "local", "extra": True},
    ],
)
def test_triage_rejects_invalid_input(payload):
    response = client.post("/api/v1/triage", json=payload)

    assert response.status_code == 422


def test_comparison_uses_same_input_without_creating_notices(
    use_mock_provider_for_contract_tests,
):
    repository = use_mock_provider_for_contract_tests

    response = client.post(
        "/api/v1/comparisons",
        json={
            "text": "Hay agua derramada en el pasillo.",
            "location": "Almacén de demostración",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["provider"] for item in body["results"]] == [
        "local",
        "external",
    ]
    assert all(item["result"] is not None for item in body["results"])
    assert body["results"][0]["metrics"]["api_cost"] == "0"
    assert body["results"][1]["metrics"]["api_cost"] is None
    assert repository.list_notices() == ()


def test_notice_can_be_listed_and_modified_once():
    created = client.post(
        "/api/v1/triage",
        json={
            "text": "Hay agua derramada en el pasillo.",
            "provider": "local",
            "location": "Almacén de demostración",
        },
    ).json()

    listed = client.get("/api/v1/notices")

    assert listed.status_code == 200
    notice = listed.json()[0]
    assert notice["id"] == created["notice_id"]
    assert notice["text"] == "Hay agua derramada en el pasillo."
    assert notice["triage_runs"][0]["status"] == "pending_review"
    assert notice["triage_runs"][0]["review"] is None

    reviewed = client.post(
        f"/api/v1/notices/{created['notice_id']}/reviews",
        json={
            "decision": "modified",
            "reviewer": "Técnica de demostración",
            "comment": "La prioridad requiere corrección humana.",
            "expected_version": 0,
            "urgency": "alta",
            "department": "seguridad",
        },
    )

    assert reviewed.status_code == 200
    run = reviewed.json()["triage_run"]
    assert run["status"] == "modified"
    assert run["version"] == 1
    assert run["proposal"]["urgency"] == "media"
    assert run["review"]["final_classification"] == {
        "category": "otros",
        "urgency": "alta",
        "department": "seguridad",
    }

    duplicate = client.post(
        f"/api/v1/notices/{created['notice_id']}/reviews",
        json={
            "decision": "approved",
            "reviewer": "Segunda revisora",
            "comment": "Intento duplicado sintético.",
            "expected_version": 0,
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "review_conflict"
    assert duplicate.json()["request_id"] == duplicate.headers["X-Request-ID"]


def test_review_of_missing_notice_is_controlled():
    response = client.post(
        "/api/v1/notices/00000000-0000-0000-0000-000000000001/reviews",
        json={
            "decision": "rejected",
            "reviewer": "Técnica de demostración",
            "comment": "Aviso inexistente de prueba.",
            "expected_version": 0,
        },
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "notice_not_found"


def test_modified_review_without_changes_is_rejected_before_persistence():
    response = client.post(
        "/api/v1/notices/00000000-0000-0000-0000-000000000001/reviews",
        json={
            "decision": "modified",
            "reviewer": "Técnica de demostración",
            "comment": "Faltan los cambios explícitos.",
            "expected_version": 0,
        },
    )

    assert response.status_code == 422
