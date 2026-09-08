"""Pruebas del recorrido HTTP de triaje con herramienta real."""

import pytest
from fastapi.testclient import TestClient

from backend.app.api.routes_triage import get_triage_service
from backend.app.main import app
from backend.app.providers import MockTriageProvider
from backend.app.services import TriageService

client = TestClient(app)


@pytest.fixture(autouse=True)
def use_mock_provider_for_contract_tests():
    app.dependency_overrides[get_triage_service] = lambda: TriageService(
        MockTriageProvider()
    )
    try:
        yield
    finally:
        app.dependency_overrides.clear()


def test_health_reports_service_available():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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
