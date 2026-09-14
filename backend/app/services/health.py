"""Comprobaciones acotadas de las dependencias visibles de la aplicación."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

import httpx

from backend.app.core.settings import Settings
from backend.app.repositories import SQLiteNoticeRepository
from backend.app.schemas import HealthResponse, ServiceHealth
from backend.app.tools import InvalidRiskMatrixError, RiskMatrixTool

from .errors import InvalidKnowledgeBaseError
from .retrieval import PreventionKnowledgeRetriever


class HealthService:
    """Comprueba modelos y persistencia sin ejecutar inferencias."""

    def __init__(
        self,
        settings: Settings,
        repository: SQLiteNoticeRepository,
        *,
        client: httpx.Client | None = None,
        risk_matrix: RiskMatrixTool | None = None,
        knowledge_retriever: PreventionKnowledgeRetriever | None = None,
    ) -> None:
        self._settings = settings
        self._repository = repository
        self._client = client or httpx.Client(
            timeout=settings.health_check_timeout_seconds
        )
        self._risk_matrix = risk_matrix
        self._knowledge_retriever = knowledge_retriever

    def check(self) -> HealthResponse:
        """Devuelve siempre la API y conserva el orden visual de los servicios."""

        needs_ollama_inventory = bool(self._settings.local_model.strip()) or (
            self._settings.embedding_enabled
        )
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="health") as executor:
            inventory = (
                executor.submit(self._load_ollama_models)
                if needs_ollama_inventory
                else None
            )
            gemini = executor.submit(self._check_gemini)
            risk_matrix = executor.submit(self._check_risk_matrix)
            rag = executor.submit(self._check_rag)
            installed_models = inventory.result() if inventory is not None else None
            model_services = (
                self._ollama_status(installed_models),
                gemini.result(),
            )
            local_services = (risk_matrix.result(), rag.result())

        sqlite_status = (
            "available" if self._repository.is_available() else "unavailable"
        )
        services = (
            ServiceHealth(id="api", label="API FastAPI", status="available"),
            *model_services,
            ServiceHealth(
                id="sqlite",
                label="SQLite",
                status=sqlite_status,
                detail=None if sqlite_status == "available" else "no disponible",
            ),
            *local_services,
            self._embedding_status(installed_models),
        )
        required_available = all(
            service.status == "available"
            for service in services
            if service.id in {"sqlite", "risk_matrix", "rag"}
        )
        provider_available = any(
            service.status == "available"
            for service in services
            if service.id in {"ollama", "gemini"}
        )
        active_services_available = all(
            service.status != "unavailable"
            for service in services
            if service.id in {"ollama", "gemini", "embeddings"}
        )
        return HealthResponse(
            status=(
                "ok"
                if required_available
                and provider_available
                and active_services_available
                else "degraded"
            ),
            services=services,
        )

    def _load_ollama_models(self) -> set[str] | None:
        try:
            response = self._client.get(
                f"{str(self._settings.ollama_base_url).rstrip('/')}/api/tags"
            )
            response.raise_for_status()
            payload = response.json()
            models = payload.get("models") if isinstance(payload, dict) else None
            if not isinstance(models, list):
                return None
            return {
                value
                for item in models
                if isinstance(item, dict)
                for key in ("name", "model")
                if isinstance((value := item.get(key)), str)
            }
        except (httpx.HTTPError, ValueError):
            return None

    @staticmethod
    def _model_is_installed(model: str, installed: set[str]) -> bool:
        return model in installed or f"{model}:latest" in installed

    def _ollama_status(self, installed_models: set[str] | None) -> ServiceHealth:
        model = self._settings.local_model.strip()
        if not model:
            return ServiceHealth(
                id="ollama",
                label="Ollama",
                status="not_configured",
                detail="sin modelo configurado",
            )
        label = f"Ollama · {model}"
        if installed_models is None:
            return ServiceHealth(
                id="ollama",
                label=label,
                status="unavailable",
                detail="sin conexión",
            )
        if not self._model_is_installed(model, installed_models):
            return ServiceHealth(
                id="ollama",
                label=label,
                status="unavailable",
                detail="modelo no instalado",
            )
        return ServiceHealth(id="ollama", label=label, status="available")

    def _embedding_status(
        self,
        installed_models: set[str] | None,
    ) -> ServiceHealth:
        if not self._settings.embedding_enabled:
            return ServiceHealth(
                id="embeddings",
                label="Embeddings",
                status="disabled",
                detail="desactivado",
            )
        model = self._settings.embedding_model.strip()
        label = f"Embeddings · {model}"
        if installed_models is None:
            return ServiceHealth(
                id="embeddings",
                label=label,
                status="unavailable",
                detail="sin conexión",
            )
        if not self._model_is_installed(model, installed_models):
            return ServiceHealth(
                id="embeddings",
                label=label,
                status="unavailable",
                detail="modelo no instalado",
            )
        return ServiceHealth(id="embeddings", label=label, status="available")

    def _check_risk_matrix(self) -> ServiceHealth:
        try:
            (self._risk_matrix or RiskMatrixTool()).document()
        except InvalidRiskMatrixError:
            return ServiceHealth(
                id="risk_matrix",
                label="Matriz PRL",
                status="unavailable",
                detail="no disponible",
            )
        return ServiceHealth(
            id="risk_matrix",
            label="Matriz PRL",
            status="available",
        )

    def _check_rag(self) -> ServiceHealth:
        try:
            (
                self._knowledge_retriever
                or PreventionKnowledgeRetriever(
                    self._settings.knowledge_base_path,
                    max_sources=self._settings.rag_max_sources,
                )
            ).document()
        except InvalidKnowledgeBaseError:
            return ServiceHealth(
                id="rag",
                label="RAG preventivo",
                status="unavailable",
                detail="no disponible",
            )
        return ServiceHealth(
            id="rag",
            label="RAG preventivo",
            status="available",
        )

    def _check_gemini(self) -> ServiceHealth:
        model = self._settings.external_model.strip()
        api_key = self._settings.external_api_key.get_secret_value().strip()
        if not api_key or not model:
            return ServiceHealth(
                id="gemini",
                label="Gemini",
                status="not_configured",
                detail="no configurado",
            )
        label = f"Gemini · {model}"
        try:
            response = self._client.get(
                (
                    f"{str(self._settings.external_api_base_url).rstrip('/')}"
                    f"/models/{quote(model, safe='')}"
                ),
                headers={"x-goog-api-key": api_key},
            )
            response.raise_for_status()
        except httpx.HTTPError:
            return ServiceHealth(
                id="gemini",
                label=label,
                status="unavailable",
                detail="no disponible",
            )
        return ServiceHealth(id="gemini", label=label, status="available")
