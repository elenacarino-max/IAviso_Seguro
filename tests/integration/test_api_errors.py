"""Pruebas HTTP de request_id y errores estables de proveedor y herramienta."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from backend.app.api.routes_health import get_health_service
from backend.app.api.routes_triage import get_notice_repository, get_triage_service
from backend.app.main import app
from backend.app.providers import (
    GeminiTriageProvider,
    MockTriageProvider,
    ProviderConnectionError,
    ProviderRateLimitError,
)
from backend.app.repositories import PersistenceError, SQLiteNoticeRepository
from backend.app.schemas import HealthResponse, ServiceHealth
from backend.app.services import (
    ExecutionTelemetry,
    InvalidKnowledgeBaseError,
    InvalidProviderOutputError,
    TriageExecution,
    TriageService,
)
from backend.app.tools import (
    InvalidRiskMatrixError,
    InvalidToolArgumentsError,
    RequiredToolCallError,
    ToolStepLimitError,
)

client = TestClient(app)
VALID_PAYLOAD = {"text": "Hay un cable deteriorado.", "provider": "local"}


def nested_keys(value):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield key
            yield from nested_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from nested_keys(nested)


class FailingService:
    def __init__(self, error):
        self.error = error

    def execute(self, request, *, request_id):
        now = datetime.now(UTC)
        return TriageExecution(
            result=None,
            telemetry=ExecutionTelemetry(
                started_at=now,
                completed_at=now,
                latency_ms=0,
                provider_attempts=1,
                repair_attempts=0,
                input_tokens=None,
                output_tokens=None,
                total_tokens=None,
                success=False,
                json_valid=None,
                error_type=type(self.error).__name__,
            ),
            error=self.error,
        )


class FailingRepository:
    def query_notices(self, **_filters):
        raise PersistenceError("detalle interno")


class StaticHealthService:
    def check(self):
        return HealthResponse(
            services=(
                ServiceHealth(id="api", label="API FastAPI", status="available"),
                ServiceHealth(
                    id="ollama",
                    label="Ollama",
                    status="not_configured",
                    detail="sin modelo configurado",
                ),
                ServiceHealth(
                    id="gemini",
                    label="Gemini",
                    status="not_configured",
                    detail="no configurado",
                ),
                ServiceHealth(id="sqlite", label="SQLite", status="available"),
            )
        )


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path):
    repository = SQLiteNoticeRepository(tmp_path / "api-errors.db")
    app.dependency_overrides[get_notice_repository] = lambda: repository
    app.dependency_overrides[get_health_service] = lambda: StaticHealthService()
    try:
        yield
    finally:
        app.dependency_overrides.clear()


def post_with_service(service):
    app.dependency_overrides[get_triage_service] = lambda: service
    try:
        return client.post("/api/v1/triage", json=VALID_PAYLOAD)
    finally:
        app.dependency_overrides.pop(get_triage_service, None)


def assert_stable_error(response, *, status_code, code):
    assert response.status_code == status_code
    UUID(response.headers["X-Request-ID"])
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
    assert response.json()["error"]["code"] == code
    assert set(response.json()) == {"error", "request_id"}


def test_success_response_has_generated_request_id():
    app.dependency_overrides[get_triage_service] = lambda: TriageService(
        MockTriageProvider()
    )
    try:
        response = client.post("/api/v1/triage", json=VALID_PAYLOAD)
    finally:
        app.dependency_overrides.pop(get_triage_service, None)

    assert response.status_code == 200
    UUID(response.headers["X-Request-ID"])


@pytest.mark.parametrize(
    ("payload", "sensitive_value", "failed_field"),
    [
        (
            {"text": "Aviso sintético.", "provider": "persona@example.com"},
            "persona@example.com",
            "provider",
        ),
        (
            {"text": "Aviso sintético.", "provider": "612 345 678"},
            "612 345 678",
            "provider",
        ),
        (
            {"text": "Aviso sintético.", "provider": "12345678Z"},
            "12345678Z",
            "provider",
        ),
        (
            {"text": "Aviso sintético.", "provider": "X1234567L"},
            "X1234567L",
            "provider",
        ),
        (
            {
                "text": "Aviso sintético.",
                "provider": "ES91 2100 0418 4502 0005 1332",
            },
            "ES91 2100 0418 4502 0005 1332",
            "provider",
        ),
        (
            {
                "text": "A" * 4001 + " persona@example.com",
                "provider": "local",
            },
            "persona@example.com",
            "text",
        ),
    ],
)
def test_validation_error_never_reflects_sensitive_input(
    payload,
    sensitive_value,
    failed_field,
    caplog,
):
    response = client.post("/api/v1/triage", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "request_validation_error"
    assert body["request_id"] == response.headers["X-Request-ID"]
    UUID(body["request_id"])
    assert sensitive_value not in response.text
    assert sensitive_value not in repr(body)
    assert "input" not in set(nested_keys(body))
    assert "ctx" not in set(nested_keys(body))
    assert ["body", failed_field] in [
        detail["loc"] for detail in body["error"]["details"]
    ]
    assert sensitive_value not in caplog.text


def test_multiple_validation_errors_expose_only_whitelisted_metadata(caplog):
    sensitive_values = (
        "multiple@example.com",
        "612 345 678",
        "12345678Z",
        "ES91 2100 0418 4502 0005 1332",
    )
    response = client.post(
        "/api/v1/triage",
        json={
            "text": "B" * 4001 + " multiple@example.com",
            "provider": "612 345 678",
            "location": "ES91 2100 0418 4502 0005 1332" * 10,
            "12345678Z": "campo adicional",
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "request_validation_error"
    assert body["request_id"] == response.headers["X-Request-ID"]
    assert len(body["error"]["details"]) == 4
    assert {tuple(detail["loc"]) for detail in body["error"]["details"]} == {
        ("body", "text"),
        ("body", "provider"),
        ("body", "location"),
        ("body", "<field>"),
    }
    assert all(
        set(detail) == {"loc", "type", "message"}
        for detail in body["error"]["details"]
    )
    assert "input" not in set(nested_keys(body))
    assert "ctx" not in set(nested_keys(body))
    assert all(value not in response.text for value in sensitive_values)
    assert all(value not in repr(body) for value in sensitive_values)
    assert all(value not in caplog.text for value in sensitive_values)


def test_external_provider_without_api_key_fails_safely():
    service = TriageService(
        GeminiTriageProvider(
            base_url="https://example.invalid",
            api_key="",
            model="gemini-test",
            timeout_seconds=1,
            temperature=0,
            top_p=1,
            max_retries=0,
            retry_base_seconds=0,
            retry_max_seconds=0,
        )
    )
    app.dependency_overrides[get_triage_service] = lambda: service
    try:
        response = client.post(
            "/api/v1/triage",
            json={"text": "Aviso sintético.", "provider": "external"},
        )
    finally:
        app.dependency_overrides.pop(get_triage_service, None)

    assert_stable_error(
        response,
        status_code=503,
        code="provider_unavailable",
    )


@pytest.mark.parametrize(
    ("error", "status_code", "code"),
    [
        (InvalidProviderOutputError(2), 502, "invalid_provider_output"),
        (ProviderConnectionError("timeout"), 503, "provider_unavailable"),
        (ProviderRateLimitError(), 429, "provider_rate_limited"),
        (InvalidToolArgumentsError("argumentos"), 502, "invalid_tool_arguments"),
        (InvalidRiskMatrixError("matriz"), 500, "invalid_risk_matrix"),
        (
            InvalidKnowledgeBaseError("corpus"),
            500,
            "invalid_knowledge_base",
        ),
        (RequiredToolCallError("sin herramienta"), 502, "required_tool_not_executed"),
        (ToolStepLimitError("límite"), 502, "tool_step_limit_exceeded"),
    ],
)
def test_expected_failures_have_stable_responses(error, status_code, code):
    response = post_with_service(FailingService(error))

    assert_stable_error(response, status_code=status_code, code=code)


def test_rate_limit_exposes_only_safe_retry_after_value():
    response = post_with_service(FailingService(ProviderRateLimitError(30)))

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "30"


def test_server_continues_serving_after_provider_failure():
    failed = post_with_service(FailingService(InvalidProviderOutputError(2)))
    healthy = client.get("/health")

    assert failed.status_code == 502
    assert healthy.status_code == 200
    assert healthy.json()["status"] == "ok"
    assert healthy.json()["services"][0]["label"] == "API FastAPI"
    assert healthy.headers["X-Request-ID"] != failed.headers["X-Request-ID"]


def test_openapi_documents_controlled_errors():
    operation = client.get("/openapi.json").json()["paths"]["/api/v1/triage"]["post"]
    responses = operation["responses"]
    assert {"429", "500", "502", "503"} <= set(responses)


def test_persistence_failure_has_stable_response():
    app.dependency_overrides[get_notice_repository] = lambda: FailingRepository()

    response = client.get("/api/v1/notices")

    assert_stable_error(
        response,
        status_code=500,
        code="persistence_error",
    )


def test_openapi_documents_notice_and_review_endpoints():
    paths = client.get("/openapi.json").json()["paths"]

    assert "/api/v1/notices" in paths
    review = paths["/api/v1/notices/{notice_id}/reviews"]["post"]
    assert {"404", "409", "500"} <= set(review["responses"])
