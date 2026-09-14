"""Peticiones HTTP del precheck a Ollama y Gemini con transporte simulado."""

import json

import httpx

from backend.app.providers import (
    GeminiInputAssessmentProvider,
    OllamaInputAssessmentProvider,
)
from backend.app.schemas import InputAssessmentRequest


def test_ollama_precheck_uses_json_without_tools_matrix_or_rag():
    captured = {}

    def handler(request):
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": json.dumps(
                        {"sufficient": True, "questions": [], "missing_aspects": []}
                    )
                }
            },
        )

    client = httpx.Client(
        base_url="http://ollama.test/",
        transport=httpx.MockTransport(handler),
    )
    provider = OllamaInputAssessmentProvider(
        base_url="http://ollama.test",
        model="modelo-local",
        timeout_seconds=5,
        temperature=0,
        top_p=0.9,
        client=client,
    )

    result = provider.assess(
        InputAssessmentRequest(text="Fuego en el cuadro.", provider="local")
    )

    assert json.loads(result) == {
        "sufficient": True,
        "questions": [],
        "missing_aspects": [],
    }
    assert captured["model"] == "modelo-local"
    assert captured["stream"] is False
    assert "tools" not in captured
    assert "Fuego en el cuadro." in json.dumps(captured, ensure_ascii=False)
    assert "atributo demográfico" in captured["messages"][0]["content"]


def test_gemini_precheck_uses_selected_model_and_no_tools():
    captured = {}

    def handler(request):
        captured["path"] = request.url.path
        captured["key"] = request.headers["x-goog-api-key"]
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "sufficient": False,
                                            "questions": ["¿Qué peligro concreto observaste?"],
                                            "missing_aspects": ["hazard"],
                                        }
                                    )
                                }
                            ]
                        }
                    }
                ]
            },
        )

    client = httpx.Client(
        base_url="https://gemini.test/v1beta/",
        transport=httpx.MockTransport(handler),
    )
    provider = GeminiInputAssessmentProvider(
        base_url="https://gemini.test/v1beta",
        api_key="clave-prueba",
        model="gemini-prueba",
        timeout_seconds=5,
        temperature=0,
        top_p=0.9,
        max_retries=0,
        retry_base_seconds=0,
        retry_max_seconds=0,
        client=client,
        sleep=lambda _: None,
    )

    result = provider.assess(
        InputAssessmentRequest(text="Hay un problema.", provider="external")
    )

    assert json.loads(result)["sufficient"] is False
    assert captured["path"].endswith("/models/gemini-prueba:generateContent")
    assert captured["key"] == "clave-prueba"
    assert "tools" not in captured["body"]
    generation = captured["body"]["generationConfig"]
    assert generation["responseMimeType"] == "application/json"
    assert generation["responseJsonSchema"]["additionalProperties"] is False
