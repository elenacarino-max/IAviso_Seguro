"""Pruebas de salud sin conexiones reales ni exposición de secretos."""

import sqlite3

import httpx
import pytest

from backend.app.core.settings import Settings
from backend.app.repositories import SQLiteNoticeRepository
from backend.app.services import HealthService, PreventionKnowledgeRetriever
from backend.app.tools import RiskMatrixTool


def model_inventory(*models: str):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [{"name": model} for model in models]})

    return handler


def test_health_reports_models_sqlite_matrix_rag_and_embeddings(tmp_path):
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={"models": [{"name": "llama3.2:3b"}, {"name": "nomic-embed-text"}]},
            )
        assert request.url.path == "/v1beta/models/gemini-test"
        assert request.headers["x-goog-api-key"] == "secret-test"
        return httpx.Response(200, json={"name": "models/gemini-test"})

    settings = Settings(
        _env_file=None,
        local_model="llama3.2:3b",
        ollama_base_url="http://ollama.test",
        embedding_enabled=True,
        embedding_model="nomic-embed-text",
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
    assert [(item.id, item.status) for item in response.services] == [
        ("api", "available"),
        ("ollama", "available"),
        ("gemini", "available"),
        ("sqlite", "available"),
        ("risk_matrix", "available"),
        ("rag", "available"),
        ("embeddings", "available"),
    ]
    assert requested_paths.count("/api/tags") == 1
    assert "/api/embed" not in requested_paths


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

    assert response.status == "degraded"
    assert by_id["ollama"].status == "not_configured"
    assert by_id["gemini"].status == "not_configured"
    assert by_id["gemini"].detail == "no configurado"
    assert by_id["sqlite"].status == "available"
    assert by_id["risk_matrix"].status == "available"
    assert by_id["rag"].status == "available"
    assert by_id["embeddings"].status == "disabled"
    assert by_id["embeddings"].detail == "desactivado"


@pytest.mark.parametrize("matrix_contents", [None, "{}"], ids=["missing", "invalid"])
def test_invalid_or_missing_matrix_is_unavailable_and_degrades_health(
    tmp_path,
    matrix_contents,
):
    matrix_path = tmp_path / "matrix.json"
    if matrix_contents is not None:
        matrix_path.write_text(matrix_contents, encoding="utf-8")
    settings = Settings(_env_file=None, local_model="llama3.2:3b")
    service = HealthService(
        settings,
        SQLiteNoticeRepository(tmp_path / "health.db"),
        client=httpx.Client(
            transport=httpx.MockTransport(model_inventory("llama3.2:3b"))
        ),
        risk_matrix=RiskMatrixTool(matrix_path),
    )

    response = service.check()
    matrix = next(item for item in response.services if item.id == "risk_matrix")

    assert response.status == "degraded"
    assert matrix.status == "unavailable"
    assert matrix.detail == "no disponible"
    assert str(matrix_path) not in response.model_dump_json()


@pytest.mark.parametrize("corpus_contents", [None, "{}"], ids=["missing", "invalid"])
def test_invalid_or_missing_rag_is_unavailable_and_degrades_health(
    tmp_path,
    corpus_contents,
):
    corpus_path = tmp_path / "corpus.json"
    if corpus_contents is not None:
        corpus_path.write_text(corpus_contents, encoding="utf-8")
    settings = Settings(_env_file=None, local_model="llama3.2:3b")
    service = HealthService(
        settings,
        SQLiteNoticeRepository(tmp_path / "health.db"),
        client=httpx.Client(
            transport=httpx.MockTransport(model_inventory("llama3.2:3b"))
        ),
        knowledge_retriever=PreventionKnowledgeRetriever(corpus_path),
    )

    response = service.check()
    rag = next(item for item in response.services if item.id == "rag")

    assert response.status == "degraded"
    assert rag.status == "unavailable"
    assert rag.detail == "no disponible"
    assert str(corpus_path) not in response.model_dump_json()


@pytest.mark.parametrize(
    ("models", "llm_status", "embedding_status", "overall_status"),
    [
        (("llama3.2:3b", "nomic-embed-text"), "available", "available", "ok"),
        (("llama3.2:3b",), "available", "unavailable", "degraded"),
        (("nomic-embed-text",), "unavailable", "available", "degraded"),
    ],
)
def test_llm_and_embedding_models_are_checked_independently(
    tmp_path,
    models,
    llm_status,
    embedding_status,
    overall_status,
):
    settings = Settings(
        _env_file=None,
        local_model="llama3.2:3b",
        embedding_enabled=True,
        embedding_model="nomic-embed-text",
    )
    service = HealthService(
        settings,
        SQLiteNoticeRepository(tmp_path / "health.db"),
        client=httpx.Client(transport=httpx.MockTransport(model_inventory(*models))),
    )

    response = service.check()
    by_id = {item.id: item for item in response.services}

    assert by_id["ollama"].status == llm_status
    assert by_id["embeddings"].status == embedding_status
    assert response.status == overall_status


def test_enabled_embeddings_are_unavailable_when_ollama_is_down(tmp_path):
    def unavailable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("host interno", request=request)

    service = HealthService(
        Settings(
            _env_file=None,
            local_model="llama3.2:3b",
            embedding_enabled=True,
        ),
        SQLiteNoticeRepository(tmp_path / "health.db"),
        client=httpx.Client(transport=httpx.MockTransport(unavailable)),
    )

    response = service.check()
    by_id = {item.id: item for item in response.services}

    assert response.status == "degraded"
    assert by_id["ollama"].status == "unavailable"
    assert by_id["embeddings"].status == "unavailable"


def test_disabled_embeddings_do_not_degrade_an_operational_system(tmp_path):
    service = HealthService(
        Settings(
            _env_file=None,
            local_model="llama3.2:3b",
            embedding_enabled=False,
        ),
        SQLiteNoticeRepository(tmp_path / "health.db"),
        client=httpx.Client(
            transport=httpx.MockTransport(model_inventory("llama3.2:3b"))
        ),
    )

    response = service.check()

    assert response.status == "ok"
    assert next(
        item.status for item in response.services if item.id == "embeddings"
    ) == "disabled"


def test_health_does_not_persist_operational_records_or_expose_secrets(tmp_path):
    database_path = tmp_path / "health.db"
    repository = SQLiteNoticeRepository(database_path)
    secret = "secret-health-value"
    service = HealthService(
        Settings(
            _env_file=None,
            local_model="llama3.2:3b",
            external_api_key=secret,
            external_model="gemini-test",
            external_api_base_url="https://gemini.test/v1beta",
        ),
        repository,
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(503, request=request)
            )
        ),
    )

    response = service.check()

    serialized = response.model_dump_json()
    assert secret not in serialized
    assert str(database_path) not in serialized
    with sqlite3.connect(database_path) as connection:
        for table in (
            "notices",
            "triage_runs",
            "notice_embeddings",
            "comparisons",
            "comparison_runs",
            "reviews",
            "audit_events",
        ):
            assert connection.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0] == 0
