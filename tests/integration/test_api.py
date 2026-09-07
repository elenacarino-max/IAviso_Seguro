"""Pruebas del recorrido HTTP mínimo de la Fase 1."""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_health_reports_service_available():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("provider", ["local", "external"])
def test_triage_returns_valid_mock_proposal(provider):
    response = client.post(
        "/api/v1/triage",
        json={
            "text": "Hay agua derramada en el pasillo.",
            "provider": provider,
            "location": "Almacén de demostración",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "category": "otros",
        "urgency": "media",
        "summary": "Aviso recibido correctamente y preparado para revisión humana del técnico.",
        "department": "prevencion",
        "justification": (
            "Respuesta simulada de la Fase 1 para Almacén de demostración; "
            "todavía no procede de un modelo real."
        ),
    }


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
