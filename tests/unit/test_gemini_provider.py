"""Pruebas del adaptador Gemini con transporte y pausas simulados."""

import json

import httpx
import pytest

from backend.app.providers import (
    GeminiTriageProvider,
    ProviderConnectionError,
    ProviderRateLimitError,
    RepairContext,
    ToolCall,
)
from backend.app.schemas import TriageRequest
from backend.app.services import TriageService
from backend.app.tools import RiskMatrixTool


def make_provider(handler, **overrides):
    sleeps = []
    client = httpx.Client(
        base_url="https://gemini.test/v1beta/",
        transport=httpx.MockTransport(handler),
    )
    options = {
        "base_url": "https://gemini.test/v1beta",
        "api_key": "clave-de-prueba",
        "model": "gemini-3.5-flash-lite",
        "timeout_seconds": 5,
        "temperature": 0,
        "top_p": 0.9,
        "max_retries": 2,
        "retry_base_seconds": 0.25,
        "retry_max_seconds": 3,
        "client": client,
        "sleep": sleeps.append,
    }
    options.update(overrides)
    return GeminiTriageProvider(**options), sleeps


@pytest.fixture
def triage_request():
    return TriageRequest(
        text="Hay humo junto a una salida.",
        provider="external",
        location="Zona sintética",
    )


def function_call_response(category="incendio", *, usage=True):
    payload = {
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [
                        {
                            "functionCall": {
                                "id": "call-risk-matrix-1",
                                "name": "consultar_matriz_riesgos",
                                "args": {"category": category},
                            },
                            "thoughtSignature": "firma-opaca-de-prueba",
                        }
                    ],
                }
            }
        ]
    }
    if usage:
        payload["usageMetadata"] = {
            "promptTokenCount": 101,
            "candidatesTokenCount": 7,
            "totalTokenCount": 108,
        }
    return payload


def tool_call_with_context(category="incendio"):
    payload = function_call_response(category, usage=False)
    content = payload["candidates"][0]["content"]
    return ToolCall(
        name="consultar_matriz_riesgos",
        arguments={"category": category},
        provider_context=content,
    )


def test_first_step_forces_only_the_risk_matrix_tool(triage_request):
    captured = {}

    def handler(http_request):
        captured["path"] = http_request.url.path
        captured["key"] = http_request.headers["x-goog-api-key"]
        captured["body"] = json.loads(http_request.content)
        return httpx.Response(200, json=function_call_response())

    provider, sleeps = make_provider(handler)
    result = provider.generate(triage_request)

    assert result == ToolCall(
        name="consultar_matriz_riesgos",
        arguments={"category": "incendio"},
    )
    assert captured["path"].endswith(
        "/models/gemini-3.5-flash-lite:generateContent"
    )
    assert captured["key"] == "clave-de-prueba"
    body = captured["body"]
    declaration = body["tools"][0]["functionDeclarations"][0]
    assert declaration["name"] == "consultar_matriz_riesgos"
    assert declaration["parametersJsonSchema"]["additionalProperties"] is False
    config = body["toolConfig"]["functionCallingConfig"]
    assert config == {
        "mode": "ANY",
        "allowedFunctionNames": ["consultar_matriz_riesgos"],
    }
    assert "responseMimeType" not in body["generationConfig"]
    assert triage_request.text in json.dumps(body, ensure_ascii=False)
    assert "atributo demográfico" in body["systemInstruction"]["parts"][0]["text"]
    assert provider.last_usage.input_tokens == 101
    assert provider.last_call_metrics.provider_attempts == 1
    assert provider.last_call_metrics.input_tokens == 101
    assert provider.last_call_metrics.output_tokens == 7
    assert provider.last_call_metrics.success is True
    assert sleeps == []


def test_complete_external_flow_returns_the_shared_contract(triage_request):
    requests = []
    valid_result = {
        "category": "incendio",
        "urgency": "critica",
        "summary": (
            "Humo visible junto a salida requiere revisión profesional inmediata "
            "preventiva."
        ),
        "department": "seguridad",
        "justification": (
            "Matriz 1.0.0, regla RM-INCE-001; requiere revisión profesional."
        ),
    }
    responses = [
        function_call_response(),
        {
            "candidates": [
                {"content": {"parts": [{"text": json.dumps(valid_result)}]}}
            ],
            "usageMetadata": {
                "promptTokenCount": 202,
                "candidatesTokenCount": 31,
                "totalTokenCount": 233,
            },
        },
    ]

    def handler(http_request):
        requests.append(json.loads(http_request.content))
        return httpx.Response(200, json=responses.pop(0))

    provider, sleeps = make_provider(handler)
    result = TriageService(provider).triage(triage_request, request_id="req-external")

    assert result.model_dump(mode="json") == valid_result
    assert len(requests) == 2
    assert requests[1]["contents"][1] == function_call_response(usage=False)[
        "candidates"
    ][0]["content"]
    assert provider.last_usage.total_tokens == 233
    assert sleeps == []


def test_final_step_requests_json_schema_and_includes_tool_evidence(triage_request):
    captured = {}
    valid_result = {
        "category": "incendio",
        "urgency": "critica",
        "summary": (
            "Humo visible junto a salida requiere revisión profesional inmediata "
            "preventiva."
        ),
        "department": "seguridad",
        "justification": (
            "Matriz 1.0.0, regla RM-INCE-001; requiere revisión profesional."
        ),
    }

    def handler(http_request):
        captured.update(json.loads(http_request.content))
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": json.dumps(valid_result)}]}}
                ]
            },
        )

    observation = RiskMatrixTool().execute({"category": "incendio"})
    provider, _ = make_provider(handler)
    result = provider.generate(
        triage_request,
        observation=observation,
        tool_call=tool_call_with_context(),
    )

    assert json.loads(result) == valid_result
    assert "tools" not in captured
    assert captured["generationConfig"]["responseMimeType"] == "application/json"
    assert captured["generationConfig"]["responseJsonSchema"]["properties"]
    serialized = json.dumps(captured, ensure_ascii=False)
    assert "functionResponse" in serialized
    assert "RM-INCE-001" in serialized
    assert "firma-opaca-de-prueba" in serialized
    assert serialized.count("call-risk-matrix-1") == 2
    assert provider.last_usage.input_tokens is None
    assert provider.last_usage.output_tokens is None
    assert provider.last_usage.total_tokens is None


def test_repair_feedback_is_separate_and_contains_contract_errors(triage_request):
    captured = {}

    def handler(http_request):
        captured.update(json.loads(http_request.content))
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "{}"}]}}]},
        )

    provider, _ = make_provider(handler)
    observation = RiskMatrixTool().execute({"category": "incendio"})
    provider.generate(
        triage_request,
        observation=observation,
        tool_call=tool_call_with_context(),
        repair=RepairContext(
            invalid_output="{}",
            validation_errors=("summary:missing",),
        ),
    )

    serialized = json.dumps(captured, ensure_ascii=False)
    assert "summary:missing" in serialized
    assert "SALIDA RECHAZADA" in serialized


def test_transient_http_failure_retries_with_exponential_backoff(triage_request):
    calls = 0

    def handler(http_request):
        nonlocal calls
        calls += 1
        if calls < 3:
            return httpx.Response(503, json={"error": "interno"})
        return httpx.Response(200, json=function_call_response())

    provider, sleeps = make_provider(handler)
    result = provider.generate(triage_request)

    assert isinstance(result, ToolCall)
    assert calls == 3
    assert sleeps == [0.25, 0.5]
    assert provider.last_call_metrics.provider_attempts == 3


def test_rate_limit_honors_bounded_retry_after_then_recovers(triage_request):
    calls = 0

    def handler(http_request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "9"})
        return httpx.Response(200, json=function_call_response())

    provider, sleeps = make_provider(handler)
    provider.generate(triage_request)

    assert calls == 2
    assert sleeps == [3]


def test_exhausted_rate_limit_preserves_valid_retry_after(triage_request):
    calls = 0

    def handler(http_request):
        nonlocal calls
        calls += 1
        return httpx.Response(429, headers={"Retry-After": "7"})

    provider, sleeps = make_provider(handler)
    with pytest.raises(ProviderRateLimitError) as captured:
        provider.generate(triage_request)

    assert calls == 3
    assert sleeps == [3, 3]
    assert captured.value.retry_after_seconds == 7
    assert provider.last_call_metrics.provider_attempts == 3
    assert provider.last_call_metrics.success is False


def test_non_transient_http_error_is_not_retried(triage_request):
    calls = 0

    def handler(http_request):
        nonlocal calls
        calls += 1
        return httpx.Response(400, json={"error": "no registrar"})

    provider, sleeps = make_provider(handler)
    with pytest.raises(ProviderConnectionError):
        provider.generate(triage_request)

    assert calls == 1
    assert sleeps == []


def test_timeout_retries_until_exhausted(triage_request):
    calls = 0

    def handler(http_request):
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("demasiado lento", request=http_request)

    provider, sleeps = make_provider(handler)
    with pytest.raises(ProviderConnectionError):
        provider.generate(triage_request)

    assert calls == 3
    assert sleeps == [0.25, 0.5]


@pytest.mark.parametrize("field", ["api_key", "model"])
def test_missing_external_configuration_fails_without_network(triage_request, field):
    calls = 0

    def handler(http_request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=function_call_response())

    provider, _ = make_provider(handler, **{field: "  "})
    with pytest.raises(ProviderConnectionError):
        provider.generate(triage_request)

    assert calls == 0


@pytest.mark.parametrize(
    "status",
    [408, 500, 502, 503, 504],
)
def test_transient_http_errors_exhaust_to_controlled_error(triage_request, status):
    def handler(http_request):
        return httpx.Response(status, json={"error": "interno"})

    provider, _ = make_provider(handler, max_retries=0)
    with pytest.raises(ProviderConnectionError):
        provider.generate(triage_request)
