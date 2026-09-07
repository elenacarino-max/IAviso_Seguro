"""Pruebas de que FastAPI valida antes de ejecutar el triaje."""

from unittest.mock import Mock

from fastapi.testclient import TestClient

from backend.app.api.routes_triage import get_triage_service
from backend.app.main import app
from backend.app.services import TriageService

client = TestClient(app)


def test_invalid_input_does_not_reach_triage_service():
    service = Mock(spec=TriageService)
    app.dependency_overrides[get_triage_service] = lambda: service

    try:
        response = client.post(
            "/api/v1/triage",
            json={"text": "", "provider": "local"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    service.triage.assert_not_called()
