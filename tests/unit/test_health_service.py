"""Pruebas de salud sin conexiones reales ni exposición de secretos."""

import httpx

from backend.app.core.settings import Settings
from backend.app.repositories import SQLiteNoticeRepository
from backend.app.services import HealthService


def test_health_reports_both_models_and_sqlite(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={"models": [{"name": "llama3.2:3b"}]},
            )
        assert request.url.path == "/v1beta/models/gemini-test"
        assert request.headers["x-goog-api-key"] == "secret-test"
        return httpx.Response(200, json={"name": "models/gemini-test"})

    settings = Settings(
        _env_file=None,
        local_model="llama3.2:3b",
        ollama_base_url="http://ollama.test",
        external_api_key="secret-test",
        external_model="gemini-test",
        external_api_base_url="https://gemini.test/v1beta",
    )
    service = HealthService(
        settings,
        SQLiteNoticeRepository(tmp_path / "health.db"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    response = service.check()

    assert response.status == "ok"
    assert [(item.id, item.label, item.status) for item in response.services] == [
        ("api", "API FastAPI", "available"),
        ("ollama", "Ollama · llama3.2:3b", "available"),
        ("gemini", "Gemini · gemini-test", "available"),
        ("sqlite", "SQLite", "available"),
    ]


def test_health_marks_unconfigured_models_without_network_calls(tmp_path):
    def unexpected_request(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("No debe consultar proveedores sin configurar.")

    service = HealthService(
        Settings(_env_file=None, local_model="", external_api_key=""),
        SQLiteNoticeRepository(tmp_path / "health.db"),
        client=httpx.Client(transport=httpx.MockTransport(unexpected_request)),
    )

    response = service.check()
    by_id = {item.id: item for item in response.services}

    assert by_id["ollama"].status == "not_configured"
    assert by_id["gemini"].status == "not_configured"
    assert by_id["gemini"].detail == "no configurado"
    assert by_id["sqlite"].status == "available"
