"""Pruebas del recorrido HTTP de triaje con herramienta real."""

import sqlite3
from threading import Barrier, Lock, get_ident

import pytest
from fastapi.testclient import TestClient

from backend.app.api.routes_health import get_health_service
from backend.app.api.routes_triage import (
    get_notice_repository,
    get_similarity_service,
    get_triage_service,
)
from backend.app.main import app
from backend.app.providers import MockTriageProvider, ToolCall
from backend.app.repositories import SQLiteNoticeRepository
from backend.app.schemas import HealthResponse, ServiceHealth
from backend.app.services import SimilarityService, TriageService

client = TestClient(app)


class StaticHealthService:
    def check(self):
        return HealthResponse(
            services=(
                ServiceHealth(id="api", label="API FastAPI", status="available"),
                ServiceHealth(
                    id="ollama",
                    label="Ollama · llama3.2:3b",
                    status="available",
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


class ConcurrentProbeProvider:
    """Solo finaliza si las dos ejecuciones alcanzan juntas cada paso."""

    def __init__(self) -> None:
        self.barrier = Barrier(2, timeout=2)
        self.thread_ids: set[int] = set()

    def generate(self, request, *, observation=None, repair=None, tool_call=None):
        self.thread_ids.add(get_ident())
        self.barrier.wait()
        if observation is None:
            return ToolCall(
                name="consultar_matriz_riesgos",
                arguments={"category": "otros"},
            )
        return {
            "category": "otros",
            "urgency": "media",
            "summary": (
                "Aviso recibido correctamente y preparado para revisión humana del técnico."
            ),
            "department": "prevencion",
            "justification": (
                "Matriz didáctica y propuesta pendiente de revisión profesional."
            ),
        }


class RecordingProvider(MockTriageProvider):
    """Conserva únicamente las entradas de prueba recibidas por el proveedor."""

    def __init__(self) -> None:
        self.received_texts: list[str] = []
        self.received_locations: list[str | None] = []
        self._lock = Lock()

    def generate(self, request, *, observation=None, repair=None, tool_call=None):
        with self._lock:
            self.received_texts.append(request.text)
            self.received_locations.append(request.location)
        return super().generate(
            request,
            observation=observation,
            repair=repair,
            tool_call=tool_call,
        )


class CategoryProvider(MockTriageProvider):
    """Fuerza una categoría cerrada y deja que la matriz determine la urgencia."""

    def __init__(self, category) -> None:
        self._category = category

    def generate(self, request, *, observation=None, repair=None, tool_call=None):
        if observation is None:
            return ToolCall(
                name="consultar_matriz_riesgos",
                arguments={"category": self._category},
            )
        return super().generate(
            request,
            observation=observation,
            repair=repair,
            tool_call=tool_call,
        )


class MatrixContradictingProvider:
    """Devuelve siempre una propuesta válida en forma, pero incoherente con matriz."""

    def generate(self, request, *, observation=None, repair=None, tool_call=None):
        if observation is None:
            return ToolCall(
                name="consultar_matriz_riesgos",
                arguments={"category": "otros"},
            )
        return {
            "category": "otros",
            "urgency": "baja",
            "summary": (
                "Aviso recibido correctamente y preparado para revisión humana del técnico."
            ),
            "department": "seguridad",
            "justification": "Propuesta sintética que contradice la matriz de prueba.",
        }


class DeterministicEmbeddingProvider:
    """Embedding pequeño y controlable para pruebas de extremo a extremo."""

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.received_texts: list[str] = []

    def embed(self, text: str) -> tuple[float, ...]:
        self.received_texts.append(text)
        if self.fail:
            raise RuntimeError("fallo sintético de embeddings")
        if "extintor" in text.casefold():
            return (0.0, 1.0)
        if "tropezado" in text.casefold():
            return (0.98, 0.2)
        return (1.0, 0.0)


def enable_similarity(provider, *, threshold: float = 0.75) -> None:
    app.dependency_overrides[get_similarity_service] = lambda: SimilarityService(
        provider,
        enabled=True,
        model="embed-test",
        threshold=threshold,
        top_k=3,
    )


@pytest.fixture(autouse=True)
def use_mock_provider_for_contract_tests(tmp_path):
    repository = SQLiteNoticeRepository(tmp_path / "api-test.db")
    app.dependency_overrides[get_triage_service] = lambda: TriageService(
        MockTriageProvider()
    )
    app.dependency_overrides[get_notice_repository] = lambda: repository
    app.dependency_overrides[get_health_service] = lambda: StaticHealthService()
    try:
        yield repository
    finally:
        app.dependency_overrides.clear()


def test_health_reports_service_available():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "services": [
            {
                "id": "api",
                "label": "API FastAPI",
                "status": "available",
                "detail": None,
            },
            {
                "id": "ollama",
                "label": "Ollama · llama3.2:3b",
                "status": "available",
                "detail": None,
            },
            {
                "id": "gemini",
                "label": "Gemini",
                "status": "not_configured",
                "detail": "no configurado",
            },
            {
                "id": "sqlite",
                "label": "SQLite",
                "status": "available",
                "detail": None,
            },
        ],
    }


def test_catalogs_endpoint_exposes_the_exact_closed_domain():
    response = client.get("/api/v1/catalogs")

    assert response.status_code == 200
    assert response.json() == {
        "categories": [
            "riesgo_electrico",
            "caidas_obstaculos",
            "incendio",
            "maquinaria",
            "sustancias_peligrosas",
            "problemas_estructurales",
            "falta_epi",
            "ergonomia",
            "otros",
        ],
        "urgencies": ["baja", "media", "alta", "critica"],
        "departments": [
            "prevencion",
            "mantenimiento",
            "seguridad",
            "limpieza",
        ],
    }


def test_removed_precheck_endpoint_is_not_exposed_in_openapi():
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/api/v1/triage/precheck" not in response.json()["paths"]


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


def test_knowledge_base_endpoint_exposes_only_safe_source_metadata():
    response = client.get("/api/v1/knowledge-base")

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == "1.0.0"
    assert body["source_format"] == "versioned_json"
    assert body["document_count"] == 10
    assert len(body["sources"]) == body["document_count"]
    assert {source["source_id"] for source in body["sources"]} >= {
        "PRL-EL-04",
        "GUIA-CUADROS-02",
    }
    assert all("content" not in source for source in body["sources"])


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
    assert result["metrics"]["evidence"][0]["source_type"] == "risk_matrix"
    assert result["metrics"]["evidence"][0]["source_id"] == "RM-OTRO-001"
    assert result["metrics"]["evidence"][1]["source_id"] == "GUIA-OBS-01"
    assert result["category"] == "otros"
    assert result["urgency"] == "media"
    assert result["department"] == "prevencion"
    assert result["summary"] == (
        "Aviso recibido correctamente y preparado para revisión humana del técnico."
    )
    assert "Matriz didáctica 1.0.0, regla RM-OTRO-001" in result["justification"]
    assert "revisión profesional" in result["justification"]
    assert result["privacy"] == {
        "redacted": False,
        "redaction_count": 0,
        "redaction_types": [],
    }
    assert result["similarity"] == {
        "available": False,
        "has_similar": False,
        "match_count": 0,
        "matches": [],
    }
    assert result["uncertainty"] == {
        "level": "medium",
        "reasons": ["generic_category"],
    }
    assert result["review_priority"] == {
        "level": "medium",
        "reasons": ["medium_urgency"],
    }
    assert result["review_policy_version"] == "v1"


def test_matrix_incoherent_proposal_is_never_persisted(
    use_mock_provider_for_contract_tests,
):
    repository = use_mock_provider_for_contract_tests
    app.dependency_overrides[get_triage_service] = lambda: TriageService(
        MatrixContradictingProvider(),
        max_repair_attempts=1,
    )

    response = client.post(
        "/api/v1/triage",
        json={"text": "Aviso sintético incoherente.", "provider": "local"},
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "invalid_provider_output"
    assert repository.list_notices() == ()


@pytest.mark.parametrize(
    "text",
    [
        "Fuego en cuadro eléctrico.",
        "Cable caído en cocina, dos personas han tropezado esta mañana.",
        "La protección de la prensa está retirada.",
        "Derrame corrosivo en taller.",
    ],
)
def test_short_notices_go_directly_to_triage_without_a_preliminary_gate(text):
    provider = RecordingProvider()
    app.dependency_overrides[get_triage_service] = lambda: TriageService(provider)

    response = client.post(
        "/api/v1/triage",
        json={"text": text, "provider": "local"},
    )

    assert response.status_code == 200
    assert provider.received_texts
    assert set(provider.received_texts) == {text}


def test_triage_anonymizes_before_provider_persistence_and_logs(
    use_mock_provider_for_contract_tests,
    caplog,
):
    repository = use_mock_provider_for_contract_tests
    provider = RecordingProvider()
    app.dependency_overrides[get_triage_service] = lambda: TriageService(provider)
    original_values = ("12345678Z", "juan@email.com")

    response = client.post(
        "/api/v1/triage",
        json={
            "text": (
                "El trabajador con DNI 12345678Z y correo juan@email.com "
                "ha sufrido una caída."
            ),
            "provider": "external",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["privacy"] == {
        "redacted": True,
        "redaction_count": 2,
        "redaction_types": ["EMAIL", "DNI_NIE"],
    }
    expected = (
        "El trabajador con DNI [DNI_NIE] y correo [EMAIL] ha sufrido una caída."
    )
    assert provider.received_texts
    assert set(provider.received_texts) == {expected}
    notices = repository.list_notices()
    assert len(notices) == 1
    assert notices[0].text == expected
    assert notices[0].triage_runs[0].review_policy_version == "v1"
    assert all(value not in response.text for value in original_values)
    assert all(value not in caplog.text for value in original_values)


def test_embedding_receives_only_sanitized_text_and_is_linked_to_notice(
    use_mock_provider_for_contract_tests,
):
    repository = use_mock_provider_for_contract_tests
    embedding_provider = DeterministicEmbeddingProvider()
    enable_similarity(embedding_provider)

    response = client.post(
        "/api/v1/triage",
        json={
            "text": "Cable junto a juan@email.com y DNI 12345678Z.",
            "provider": "local",
            "location": " ALMACÉN ",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert embedding_provider.received_texts == [
        "Cable junto a [EMAIL] y DNI [DNI_NIE]."
    ]
    assert body["similarity"]["available"] is True
    embeddings = repository.list_notice_embeddings("embed-test")
    assert len(embeddings) == 1
    assert str(embeddings[0].notice_id) == body["notice_id"]
    assert embeddings[0].model == "embed-test"
    assert embeddings[0].dimensions == 2


def test_embedding_failure_does_not_block_triage(
    use_mock_provider_for_contract_tests,
    caplog,
):
    repository = use_mock_provider_for_contract_tests
    enable_similarity(DeterministicEmbeddingProvider(fail=True))

    response = client.post(
        "/api/v1/triage",
        json={
            "text": "Aviso operativo de juan@email.com",
            "provider": "local",
        },
    )

    assert response.status_code == 200
    assert response.json()["similarity"]["available"] is False
    assert response.json()["review_priority"]["level"] == "medium"
    assert len(repository.list_notices()) == 1
    assert repository.list_notice_embeddings("embed-test") == ()
    assert "juan@email.com" not in caplog.text
    assert "Aviso operativo" not in caplog.text
    assert "[EMAIL]" not in caplog.text


def test_later_notice_finds_similar_history_but_not_unrelated_notice(
    use_mock_provider_for_contract_tests,
):
    embedding_provider = DeterministicEmbeddingProvider()
    enable_similarity(embedding_provider, threshold=0.9)
    first = client.post(
        "/api/v1/triage",
        json={
            "text": "Cable suelto en el pasillo del almacén.",
            "provider": "local",
            "location": "Almacén",
        },
    ).json()

    related = client.post(
        "/api/v1/triage",
        json={
            "text": "Dos trabajadores han tropezado con un cable.",
            "provider": "local",
            "location": " almacén ",
        },
    ).json()
    unrelated = client.post(
        "/api/v1/triage",
        json={
            "text": "Extintor sin señalizar en oficinas.",
            "provider": "local",
            "location": "Oficinas",
        },
    ).json()

    assert related["similarity"]["has_similar"] is True
    assert related["similarity"]["matches"][0]["notice_id"] == first["notice_id"]
    assert related["similarity"]["matches"][0]["same_location"] is True
    assert related["review_priority"]["level"] == "high"
    assert "recurrent_same_location" in related["review_priority"]["reasons"]
    assert unrelated["similarity"]["has_similar"] is False


def test_comparison_and_benchmark_never_generate_or_persist_embeddings(
    use_mock_provider_for_contract_tests,
):
    repository = use_mock_provider_for_contract_tests
    embedding_provider = DeterministicEmbeddingProvider()
    enable_similarity(embedding_provider)

    comparison = client.post(
        "/api/v1/comparisons",
        json={"text": "Caso comparativo sintético"},
    )
    benchmark = client.post("/api/v1/evaluations")

    assert comparison.status_code == 200
    assert benchmark.status_code == 200
    assert embedding_provider.received_texts == []
    assert repository.list_notice_embeddings("embed-test") == ()


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
    assert body["privacy"]["redacted"] is False
    assert "review_priority" not in body
    assert all("review_priority" not in item for item in body["results"])
    assert repository.list_notices() == ()


def test_comparison_applies_the_same_privacy_policy(
    use_mock_provider_for_contract_tests,
):
    repository = use_mock_provider_for_contract_tests
    provider = RecordingProvider()
    app.dependency_overrides[get_triage_service] = lambda: TriageService(provider)

    response = client.post(
        "/api/v1/comparisons",
        json={
            "text": "Usar ES91 2100 0418 4502 0005 1332.",
            "location": "Contacto 612 345 678",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["privacy"] == {
        "redacted": True,
        "redaction_count": 2,
        "redaction_types": ["PHONE", "IBAN"],
    }
    expected = "Usar [IBAN]."
    assert len(provider.received_texts) == 4
    assert set(provider.received_texts) == {expected}
    assert set(provider.received_locations) == {"Contacto [PHONE]"}
    with sqlite3.connect(repository._database_path) as connection:
        stored_text, stored_location = connection.execute(
            "SELECT text, location FROM comparisons"
        ).fetchone()
    assert (stored_text, stored_location) == (expected, "Contacto [PHONE]")
    assert "612 345 678" not in response.text
    assert "ES91 2100 0418 4502 0005 1332" not in response.text


def test_comparison_executes_both_providers_concurrently(
    use_mock_provider_for_contract_tests,
):
    probe = ConcurrentProbeProvider()
    app.dependency_overrides[get_triage_service] = lambda: TriageService(probe)

    response = client.post(
        "/api/v1/comparisons",
        json={"text": "Caso sintético concurrente"},
    )

    assert response.status_code == 200
    assert [item["provider"] for item in response.json()["results"]] == [
        "local",
        "external",
    ]
    assert len(probe.thread_ids) == 2


def test_evaluation_exposes_quality_latency_and_cost_without_creating_notices(
    use_mock_provider_for_contract_tests,
):
    repository = use_mock_provider_for_contract_tests

    response = client.post("/api/v1/evaluations")

    assert response.status_code == 200
    body = response.json()
    assert body["dataset_version"] == "1.0.0"
    assert [item["provider"] for item in body["summaries"]] == [
        "local",
        "external",
    ]
    assert all(item["cases"] == 14 for item in body["summaries"])
    assert all(item["evaluated_cases"] == 14 for item in body["summaries"])
    assert all(item["failed_cases"] == 0 for item in body["summaries"])
    assert all(item["category_accuracy"] is not None for item in body["summaries"])
    assert all(item["urgency_accuracy"] is not None for item in body["summaries"])
    assert all(item["department_accuracy"] is not None for item in body["summaries"])
    assert all(item["mean_latency_ms"] is not None for item in body["summaries"])
    assert body["summaries"][0]["mean_api_cost"] == "0"
    assert all("review_priority" not in item for item in body["summaries"])
    assert repository.list_notices() == ()


def test_metrics_summary_compares_providers_against_human_reviews():
    local = client.post(
        "/api/v1/triage",
        json={"text": "Caso sintético local", "provider": "local"},
    ).json()
    external = client.post(
        "/api/v1/triage",
        json={"text": "Caso sintético externo", "provider": "external"},
    ).json()
    client.post(
        f"/api/v1/notices/{local['notice_id']}/reviews",
        json={
            "decision": "approved",
            "reviewer": "Técnica demo",
            "comment": "La propuesta coincide.",
            "expected_version": 0,
        },
    )
    client.post(
        f"/api/v1/notices/{external['notice_id']}/reviews",
        json={
            "decision": "modified",
            "reviewer": "Técnica demo",
            "comment": "Se corrige la urgencia.",
            "expected_version": 0,
            "urgency": "alta",
        },
    )

    response = client.get("/api/v1/metrics/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["total_notices"] == 2
    assert body["reviewed"] == 2
    assert body["acceptance_rate"] == 0.5
    assert body["correction_rate"] == 0.5
    assert body["review_policy_observations"] == 2
    assert [item["level"] for item in body["uncertainty"]] == [
        "low",
        "medium",
        "high",
    ]
    medium = next(item for item in body["uncertainty"] if item["level"] == "medium")
    assert medium["rate"] == 1
    assert medium["reviewed_runs"] == 2
    assert medium["human_correction_rate"] == 0.5
    by_provider = {item["provider"]: item for item in body["providers"]}
    assert by_provider["local"]["human_agreement_rate"] == 1
    assert by_provider["external"]["human_agreement_rate"] == 0
    assert by_provider["local"]["mean_latency_ms"] is not None
    assert by_provider["local"]["repair_rate"] == 0


def test_comparison_accepts_one_human_reference(use_mock_provider_for_contract_tests):
    repository = use_mock_provider_for_contract_tests
    comparison = client.post(
        "/api/v1/comparisons",
        json={"text": "Caso sintético común"},
    ).json()
    payload = {
        "category": "otros",
        "urgency": "media",
        "department": "prevencion",
        "reviewer": "Técnica demo",
        "comment": "Referencia humana para comparar ambos modelos.",
    }

    response = client.post(
        f"/api/v1/comparisons/{comparison['comparison_id']}/review",
        json=payload,
    )

    assert response.status_code == 200
    assert response.json()["category"] == "otros"
    assert response.json()["comparison_id"] == comparison["comparison_id"]
    duplicate = client.post(
        f"/api/v1/comparisons/{comparison['comparison_id']}/review",
        json=payload,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "comparison_review_conflict"
    assert repository.list_notices() == ()


def test_metrics_summary_includes_reviewed_comparison_executions():
    comparison = client.post(
        "/api/v1/comparisons",
        json={"text": "Caso sintético común"},
    ).json()
    client.post(
        f"/api/v1/comparisons/{comparison['comparison_id']}/review",
        json={
            "category": "otros",
            "urgency": "media",
            "department": "prevencion",
            "reviewer": "Técnica demo",
            "comment": "La clasificación coincide con ambos modelos.",
        },
    )

    response = client.get("/api/v1/metrics/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["total_notices"] == 0
    assert body["total_runs"] == 2
    assert all(item["runs"] == 1 for item in body["providers"])
    assert all(item["reviewed_runs"] == 1 for item in body["providers"])
    assert all(item["human_agreement_rate"] == 1 for item in body["providers"])
    assert all(item["success_rate"] == 1 for item in body["providers"])
    assert body["review_policy_observations"] == 0


def test_metrics_summary_counts_pending_critical_review_priority():
    app.dependency_overrides[get_triage_service] = lambda: TriageService(
        CategoryProvider("incendio")
    )

    created = client.post(
        "/api/v1/triage",
        json={"text": "Hay fuego en el cuadro eléctrico.", "provider": "local"},
    )
    summary = client.get("/api/v1/metrics/summary")

    assert created.status_code == 200
    assert created.json()["review_priority"]["level"] == "critical"
    assert summary.json()["pending_critical_priority"] == 1
    assert summary.json()["pending_high_priority"] == 0


def test_preventive_metrics_use_only_human_confirmed_classifications():
    approved = client.post(
        "/api/v1/triage",
        json={
            "text": "Aviso aprobado para análisis preventivo.",
            "provider": "local",
            "location": "Almacén",
        },
    ).json()
    modified_one = client.post(
        "/api/v1/triage",
        json={
            "text": "Primer aviso corregido para análisis preventivo.",
            "provider": "local",
            "location": " almacén ",
        },
    ).json()
    modified_two = client.post(
        "/api/v1/triage",
        json={
            "text": "Segundo aviso corregido para análisis preventivo.",
            "provider": "local",
            "location": "ALMACÉN",
        },
    ).json()
    rejected = client.post(
        "/api/v1/triage",
        json={"text": "Aviso rechazado.", "provider": "local", "location": "Taller"},
    ).json()
    client.post(
        "/api/v1/triage",
        json={"text": "Aviso aún pendiente.", "provider": "local", "location": "Carga"},
    )

    client.post(
        f"/api/v1/notices/{approved['notice_id']}/reviews",
        json={
            "decision": "approved",
            "reviewer": "Técnica demo",
            "comment": "Clasificación confirmada.",
            "expected_version": 0,
        },
    )
    for created in (modified_one, modified_two):
        client.post(
            f"/api/v1/notices/{created['notice_id']}/reviews",
            json={
                "decision": "modified",
                "reviewer": "Técnica demo",
                "comment": "Clasificación preventiva corregida.",
                "expected_version": 0,
                "category": "caidas_obstaculos",
                "urgency": "alta",
            },
        )
    client.post(
        f"/api/v1/notices/{rejected['notice_id']}/reviews",
        json={
            "decision": "rejected",
            "reviewer": "Técnica demo",
            "comment": "No corresponde a un aviso preventivo confirmado.",
            "expected_version": 0,
        },
    )
    metrics_before = client.get("/api/v1/metrics/summary").json()

    response = client.get("/api/v1/metrics/preventive?window_days=all")

    assert response.status_code == 200
    body = response.json()
    assert body["period"]["window"] == "all"
    assert body["period"]["granularity"] == "month"
    assert body["totals"] == {
        "confirmed_notices": 3,
        "pending_notices": 1,
        "rejected_notices": 1,
    }
    assert body["by_location"][0] == {
        "location": "Almacén",
        "total": 3,
        "high_or_critical_urgency": 2,
    }
    assert body["by_category"] == [
        {"category": "caidas_obstaculos", "total": 2},
        {"category": "otros", "total": 1},
    ]
    assert body["location_category_hotspots"] == [
        {
            "location": "Almacén",
            "category": "caidas_obstaculos",
            "total": 2,
            "high_or_critical_urgency": 2,
        }
    ]
    assert body["pending_by_priority"]["levels"][1] == {
        "level": "medium",
        "total": 1,
    }
    assert body["enough_data_for_trends"] is True
    assert client.get("/api/v1/metrics/summary").json() == metrics_before


@pytest.mark.parametrize("window", ["7", "30", "90", "all"])
def test_preventive_metrics_accept_supported_windows(window):
    response = client.get(f"/api/v1/metrics/preventive?window_days={window}")

    assert response.status_code == 200
    assert response.json()["period"]["window"] == window


def test_preventive_metrics_reject_arbitrary_windows():
    response = client.get("/api/v1/metrics/preventive?window_days=365")

    assert response.status_code == 422


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
    page = listed.json()
    assert page["total"] == 1
    assert page["page"] == 1
    assert page["pages"] == 1
    notice = page["items"][0]
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


def test_notices_support_typed_filters_search_and_pagination():
    first = client.post(
        "/api/v1/triage",
        json={"text": "Caso alfa junto al cuadro", "provider": "local"},
    ).json()
    client.post(
        f"/api/v1/notices/{first['notice_id']}/reviews",
        json={
            "decision": "modified",
            "reviewer": "Técnica PRL",
            "comment": "Clasificación final comprobada.",
            "expected_version": 0,
            "category": "incendio",
            "urgency": "critica",
            "department": "seguridad",
        },
    )
    client.post(
        "/api/v1/triage",
        json={"text": "Caso beta en almacén", "provider": "external"},
    )

    filtered = client.get(
        "/api/v1/notices",
        params={
            "search": "alfa",
            "status": "modified",
            "urgency": "critica",
            "category": "incendio",
            "provider": "local",
            "page": 1,
            "limit": 1,
        },
    )

    assert filtered.status_code == 200
    body = filtered.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == first["notice_id"]
    assert body["items"][0]["triage_runs"][0]["status"] == "modified"
    paged = client.get("/api/v1/notices", params={"page": 1, "limit": 1})
    assert paged.json()["total"] == 2
    assert paged.json()["pages"] == 2
    assert len(paged.json()["items"]) == 1
    closed = client.get("/api/v1/notices", params={"closed": "true"})
    assert closed.json()["total"] == 1
    assert closed.json()["items"][0]["id"] == first["notice_id"]
    pending = client.get("/api/v1/notices", params={"closed": "false"})
    assert pending.json()["total"] == 1
    assert pending.json()["items"][0]["triage_runs"][0]["status"] == "pending_review"
    by_priority = client.get(
        "/api/v1/notices",
        params={"review_priority": "medium", "order": "review_priority"},
    )
    assert by_priority.status_code == 200
    assert by_priority.json()["total"] == 2
    assert client.get("/api/v1/notices", params={"status": "otro"}).status_code == 422
    assert client.get(
        "/api/v1/notices", params={"review_priority": "urgent"}
    ).status_code == 422
    assert client.get("/api/v1/notices", params={"limit": 101}).status_code == 422


def test_notice_audit_events_are_exposed_in_order():
    created = client.post(
        "/api/v1/triage",
        json={"text": "Caso trazable", "provider": "local"},
    ).json()
    client.post(
        f"/api/v1/notices/{created['notice_id']}/reviews",
        json={
            "decision": "approved",
            "reviewer": "Técnica PRL",
            "comment": "Propuesta verificada.",
            "expected_version": 0,
        },
    )

    response = client.get(
        f"/api/v1/notices/{created['notice_id']}/audit-events"
    )

    assert response.status_code == 200
    assert [item["event_type"] for item in response.json()] == [
        "triage_created",
        "review_completed",
    ]
    assert response.json()[1]["actor"] == "Técnica PRL"
    missing = client.get(
        "/api/v1/notices/00000000-0000-0000-0000-000000000001/audit-events"
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "notice_not_found"


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
