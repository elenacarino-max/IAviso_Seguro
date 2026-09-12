"""Comprobaciones acotadas de las dependencias visibles de la aplicación."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

import httpx

from backend.app.core.settings import Settings
from backend.app.repositories import SQLiteNoticeRepository
from backend.app.schemas import HealthResponse, ServiceHealth


class HealthService:
    """Comprueba modelos y persistencia sin ejecutar inferencias."""

    def __init__(
        self,
        settings: Settings,
        repository: SQLiteNoticeRepository,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings
        self._repository = repository
        self._client = client or httpx.Client(
            timeout=settings.health_check_timeout_seconds
        )

    def check(self) -> HealthResponse:
        """Devuelve siempre la API y conserva el orden visual de los servicios."""

        with ThreadPoolExecutor(
            max_workers=2,
            thread_name_prefix="health-model",
        ) as executor:
            ollama = executor.submit(self._check_ollama)
            gemini = executor.submit(self._check_gemini)
            model_services = (ollama.result(), gemini.result())

        sqlite_status = (
            "available" if self._repository.is_available() else "unavailable"
        )
        return HealthResponse(
            services=(
                ServiceHealth(
                    id="api",
                    label="API FastAPI",
                    status="available",
                ),
                *model_services,
                ServiceHealth(
                    id="sqlite",
                    label="SQLite",
                    status=sqlite_status,
                    detail=None if sqlite_status == "available" else "no disponible",
                ),
            )
        )

    def _check_ollama(self) -> ServiceHealth:
        model = self._settings.local_model.strip()
        if not model:
            return ServiceHealth(
                id="ollama",
                label="Ollama",
                status="not_configured",
                detail="sin modelo configurado",
            )
        label = f"Ollama · {model}"
        try:
            response = self._client.get(
                f"{str(self._settings.ollama_base_url).rstrip('/')}/api/tags"
            )
            response.raise_for_status()
            payload = response.json()
            models = payload.get("models") if isinstance(payload, dict) else None
            installed = {
                value
                for item in models if isinstance(item, dict)
                for key in ("name", "model")
                if isinstance((value := item.get(key)), str)
            } if isinstance(models, list) else set()
        except (httpx.HTTPError, ValueError):
            return ServiceHealth(
                id="ollama",
                label=label,
                status="unavailable",
                detail="sin conexión",
            )
        if model not in installed and f"{model}:latest" not in installed:
            return ServiceHealth(
                id="ollama",
                label=label,
                status="unavailable",
                detail="modelo no instalado",
            )
        return ServiceHealth(id="ollama", label=label, status="available")

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
