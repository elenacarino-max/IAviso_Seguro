"""Pruebas del adaptador Ollama con transporte HTTP completamente simulado."""

import json

import httpx
import pytest

from backend.app.providers import (
    OllamaTriageProvider,
    ProviderConnectionError,
    ProviderRateLimitError,
    RepairContext,
    ToolCall,
)
from backend.app.prompts.output_format import ollama_output_schema
from backend.app.schemas import TriageRequest
from backend.app.tools import RiskMatrixTool


def make_provider(handler, **overrides):
    client = httpx.Client(
        base_url="http://ollama.test/",
        transport=httpx.MockTransport(handler),
    )
    options = {
        "base_url": "http://ollama.test",
        "model": "modelo-prueba:1b",
        "timeout_seconds": 5,
        "temperature": 0.1,
        "top_p": 0.8,
        "client": client,
    }
    options.update(overrides)
    return OllamaTriageProvider(**options)


@pytest.fixture
def triage_request():
    return TriageRequest(
        text="Hay humo junto a una salida.",
        provider="local",
        location="Zona sintética",
    )


def test_first_step_requests_exactly_one_allowed_tool(triage_request):
    captured = {}

    def handler(http_request):
        captured.update(json.loads(http_request.content))
        return httpx.Response(
            200,
            json={
                "prompt_eval_count": 55,
                "eval_count": 4,
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "consultar_matriz_riesgos",
                                "arguments": {"category": "incendio"},
                            }
                        }
                    ],
                }
            },
        )

    provider = make_provider(handler)
    result = provider.generate(triage_request)

    assert result == ToolCall(
        name="consultar_matriz_riesgos",
        arguments={"category": "incendio"},
    )
    assert captured["model"] == "modelo-prueba:1b"
    assert captured["stream"] is False
    assert captured["options"] == {"temperature": 0.1, "top_p": 0.8}
    assert captured["tools"][0]["function"]["name"] == "consultar_matriz_riesgos"
    assert "format" not in captured
    assert triage_request.text in captured["messages"][2]["content"]
    assert "atributo demográfico" in captured["messages"][0]["content"]
    assert provider.last_call_metrics.input_tokens == 55
    assert provider.last_call_metrics.output_tokens == 4
    assert provider.last_call_metrics.total_tokens == 59


def test_final_step_uses_real_observation_and_pydantic_schema(triage_request):
    captured = {}
    valid_result = {
        "category": "incendio",
        "urgency": "critica",
        "summary": (
            "Humo visible junto a salida requiere revisión profesional inmediata "
            "preventiva."
        ),
        "department": "seguridad",
        "justification": "Matriz 1.0.0, regla RM-INCE-001; requiere revisión profesional.",
    }

    def handler(http_request):
        captured.update(json.loads(http_request.content))
        return httpx.Response(200, json={"message": {"content": json.dumps(valid_result)}})

    observation = RiskMatrixTool().execute({"category": "incendio"})
    result = make_provider(handler).generate(triage_request, observation=observation)

    assert json.loads(result) == valid_result
    assert captured["format"] == ollama_output_schema()
    assert captured["format"]["properties"]["category"]["enum"]
    assert "maxLength" not in captured["format"]["properties"]["summary"]
    assert "tools" not in captured
    tool_message = next(item for item in captured["messages"] if item["role"] == "tool")
    assert "RM-INCE-001" in tool_message["content"]
    assert "exactamente diez palabras" in captured["messages"][-1]["content"]


def test_repair_context_is_separate_and_contains_only_contract_feedback(triage_request):
    captured = {}

    def handler(http_request):
        captured.update(json.loads(http_request.content))
        return httpx.Response(200, json={"message": {"content": "{}"}})

    observation = RiskMatrixTool().execute({"category": "incendio"})
    make_provider(handler).generate(
        triage_request,
        observation=observation,
        repair=RepairContext(
            invalid_output="{}",
            validation_errors=("summary:missing",),
        ),
    )

    repair_message = captured["messages"][-1]["content"]
    assert "summary:missing" in repair_message
    assert "SALIDA RECHAZADA" in repair_message


def test_tool_argument_repair_is_sent_before_matrix_execution(triage_request):
    captured = {}

    def handler(http_request):
        captured.update(json.loads(http_request.content))
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "consultar_matriz_riesgos",
                                "arguments": {"category": "incendio"},
                            }
                        }
                    ],
                }
            },
        )

    result = make_provider(handler).generate(
        triage_request,
        repair=RepairContext(
            invalid_output={
                "name": "consultar_matriz_riesgos",
                "arguments": {"category": "riesgo_incendio"},
            },
            validation_errors=("tool_arguments:invalid",),
        ),
    )

    assert result == ToolCall(
        name="consultar_matriz_riesgos",
        arguments={"category": "incendio"},
    )
    assert "tool_arguments:invalid" in captured["messages"][-1]["content"]
    assert "una categoría exacta" in captured["messages"][-1]["content"]


def test_summary_word_count_repair_has_exact_safe_fallback(triage_request):
    captured = {}

    def handler(http_request):
        captured.update(json.loads(http_request.content))
        return httpx.Response(200, json={"message": {"content": "{}"}})

    observation = RiskMatrixTool().execute({"category": "incendio"})
    make_provider(handler).generate(
        triage_request,
        observation=observation,
        repair=RepairContext(
            invalid_output='{"summary":"Resumen de nueve palabras"}',
            validation_errors=(
                "summary:value_error:Value error, El resumen debe contener "
                "exactamente 10 palabras; se recibieron 4.",
            ),
        ),
    )

    repair_message = captured["messages"][-1]["content"]
    assert (
        "Aviso requiere evaluación técnica y revisión profesional antes de actuar."
        in repair_message
    )
    assert "Son 10 palabras." in repair_message


def test_timeout_becomes_controlled_connection_error(triage_request):
    def handler(http_request):
        raise httpx.ReadTimeout("demasiado lento", request=http_request)

    with pytest.raises(ProviderConnectionError):
        make_provider(handler).generate(triage_request)


@pytest.mark.parametrize("status", [404, 500, 503])
def test_ollama_http_failure_becomes_controlled_connection_error(triage_request, status):
    def handler(http_request):
        return httpx.Response(status, json={"error": "detalle interno"})

    with pytest.raises(ProviderConnectionError):
        make_provider(handler).generate(triage_request)


def test_rate_limit_preserves_only_valid_retry_after(triage_request):
    def handler(http_request):
        return httpx.Response(429, headers={"Retry-After": "7"})

    with pytest.raises(ProviderRateLimitError) as captured:
        make_provider(handler).generate(triage_request)

    assert captured.value.retry_after_seconds == 7


def test_empty_model_fails_without_making_network_request(triage_request):
    calls = 0

    def handler(http_request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"message": {"content": "{}"}})

    with pytest.raises(ProviderConnectionError):
        make_provider(handler, model="  ").generate(triage_request)

    assert calls == 0
