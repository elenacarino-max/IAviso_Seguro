"""Ejecuta demos sin credenciales, modelos instalados ni datos reales."""

from __future__ import annotations

import argparse
import json
from tempfile import TemporaryDirectory
from typing import Any

import httpx
from fastapi.testclient import TestClient

from backend.app.api.routes_triage import (
    get_metrics_service,
    get_notice_repository,
    get_triage_service,
)
from backend.app.core.settings import Settings
from backend.app.main import app
from backend.app.providers import GeminiTriageProvider, MockTriageProvider, ToolCall
from backend.app.repositories import SQLiteNoticeRepository
from backend.app.schemas import TriageRequest
from backend.app.services import MetricsService, TriageService

_VALID_RESULT = {
    "category": "riesgo_electrico",
    "urgency": "alta",
    "summary": (
        "Cable deteriorado visible junto al acceso del almacén de demostración."
    ),
    "department": "mantenimiento",
    "justification": (
        "Matriz didáctica RM-ELEC-001; propuesta pendiente de revisión profesional."
    ),
}


class _SequenceProvider:
    def __init__(self, *outputs: object) -> None:
        self._outputs = list(outputs)

    def generate(
        self,
        request,
        *,
        observation=None,
        repair=None,
        tool_call=None,
    ):
        return self._outputs.pop(0)


def run_main_demo() -> dict[str, Any]:
    """Alta, consulta y aprobación mediante los endpoints públicos."""

    with TemporaryDirectory(prefix="iaviso-demo-") as temp_directory:
        repository = SQLiteNoticeRepository(f"{temp_directory}/demo.db")
        service = TriageService(MockTriageProvider())
        metrics = MetricsService(
            Settings(_env_file=None, local_model="mock-synthetic")
        )
        app.dependency_overrides[get_notice_repository] = lambda: repository
        app.dependency_overrides[get_triage_service] = lambda: service
        app.dependency_overrides[get_metrics_service] = lambda: metrics
        try:
            with TestClient(app) as client:
                created_response = client.post(
                    "/api/v1/triage",
                    json={
                        "text": "Hay un objeto sin identificar en una zona de paso.",
                        "location": "Almacén sintético",
                        "provider": "local",
                    },
                )
                created_response.raise_for_status()
                created = created_response.json()

                listed_response = client.get("/api/v1/notices")
                listed_response.raise_for_status()
                listed = listed_response.json()

                reviewed_response = client.post(
                    f"/api/v1/notices/{created['notice_id']}/reviews",
                    json={
                        "decision": "approved",
                        "reviewer": "Técnica sintética",
                        "comment": "Propuesta revisada únicamente para la demo.",
                        "expected_version": created["version"],
                    },
                )
                reviewed_response.raise_for_status()
                reviewed = reviewed_response.json()
        finally:
            app.dependency_overrides.clear()

    return {
        "scenario": "main",
        "created_status": created["status"],
        "listed_notices": len(listed),
        "reviewed_status": reviewed["triage_run"]["status"],
        "proposal_preserved": (
            reviewed["triage_run"]["proposal"]["category"] == created["category"]
        ),
        "human_validation_required": True,
    }


def run_repair_demo() -> dict[str, Any]:
    """Salida JSON rota seguida de una única reparación válida."""

    provider = _SequenceProvider(
        ToolCall(
            name="consultar_matriz_riesgos",
            arguments={"category": "riesgo_electrico"},
        ),
        "{",
        _VALID_RESULT,
    )
    execution = TriageService(
        provider,
        max_repair_attempts=1,
    ).execute(
        TriageRequest(
            text="Hay un cable deteriorado con cobre visible.",
            location="Taller sintético",
            provider="local",
        ),
        request_id="demo-repair",
    )
    return {
        "scenario": "repair",
        "success": execution.result is not None,
        "provider_attempts": execution.telemetry.provider_attempts,
        "repair_attempts": execution.telemetry.repair_attempts,
        "json_valid": execution.telemetry.json_valid,
        "final_category": (
            execution.result.category if execution.result is not None else None
        ),
    }


def run_rate_limit_demo() -> dict[str, Any]:
    """Un 429 sintético respeta Retry-After y se recupera sin esperar realmente."""

    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "2"})
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "functionCall": {
                                        "name": "consultar_matriz_riesgos",
                                        "args": {"category": "incendio"},
                                    }
                                }
                            ]
                        }
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 80,
                    "candidatesTokenCount": 5,
                    "totalTokenCount": 85,
                },
            },
        )

    provider = GeminiTriageProvider(
        base_url="https://gemini.demo/v1beta",
        api_key="clave-sintetica",
        model="gemini-demo",
        timeout_seconds=5,
        temperature=0,
        top_p=0.9,
        max_retries=2,
        retry_base_seconds=0.25,
        retry_max_seconds=3,
        client=httpx.Client(
            base_url="https://gemini.demo/v1beta/",
            transport=httpx.MockTransport(handler),
        ),
        sleep=sleeps.append,
    )
    result = provider.generate(
        TriageRequest(
            text="Hay humo junto a una salida.",
            location="Zona sintética",
            provider="external",
        )
    )
    return {
        "scenario": "rate-limit",
        "recovered": isinstance(result, ToolCall),
        "provider_attempts": provider.last_call_metrics.provider_attempts,
        "backoff_seconds": sleeps,
        "retry_after_respected": sleeps == [2],
    }


def run_scenario(name: str) -> list[dict[str, Any]]:
    scenarios = {
        "main": run_main_demo,
        "repair": run_repair_demo,
        "rate-limit": run_rate_limit_demo,
    }
    selected = scenarios.values() if name == "all" else (scenarios[name],)
    return [scenario() for scenario in selected]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Demos sintéticas reproducibles de IAviso Seguro."
    )
    parser.add_argument(
        "--scenario",
        choices=("all", "main", "repair", "rate-limit"),
        default="all",
    )
    arguments = parser.parse_args()
    print(json.dumps(run_scenario(arguments.scenario), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
