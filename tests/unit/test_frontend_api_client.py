"""Contrato del cliente HTTP usado por Streamlit."""

import json

import httpx
import pytest

from frontend.api_client import ApiClientError, IAvisoApiClient


def test_client_completes_create_list_review_and_compare_flow():
    calls = []

    def handler(request):
        payload = json.loads(request.content) if request.content else None
        calls.append((request.method, request.url.path, payload))
        if request.url.path.endswith("/triage"):
            return httpx.Response(200, json={"notice_id": "notice-1"})
        if request.method == "GET":
            return httpx.Response(200, json=[{"id": "notice-1", "triage_runs": []}])
        if request.url.path.endswith("/reviews"):
            return httpx.Response(200, json={"notice_id": "notice-1"})
        return httpx.Response(
            200,
            json={"comparison_id": "comparison-1", "results": []},
        )

    http_client = httpx.Client(
        base_url="http://api.test/",
        transport=httpx.MockTransport(handler),
    )
    client = IAvisoApiClient("http://api.test", client=http_client)

    created = client.create_triage(
        text="Caso sintético",
        provider="local",
        location="Taller",
    )
    notices = client.list_notices()
    reviewed = client.review_notice(
        "notice-1",
        decision="approved",
        reviewer="Técnica",
        comment="Revisión sintética.",
        expected_version=0,
    )
    compared = client.compare(text="Caso sintético", location=None)

    assert created["notice_id"] == "notice-1"
    assert notices[0]["id"] == "notice-1"
    assert reviewed["notice_id"] == "notice-1"
    assert compared["comparison_id"] == "comparison-1"
    assert [path for _, path, _ in calls] == [
        "/api/v1/triage",
        "/api/v1/notices",
        "/api/v1/notices/notice-1/reviews",
        "/api/v1/comparisons",
    ]
    assert calls[0][2] == {
        "text": "Caso sintético",
        "provider": "local",
        "location": "Taller",
    }


def test_modified_review_sends_explicit_final_classification():
    captured = {}

    def handler(request):
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"notice_id": "notice-1"})

    client = IAvisoApiClient(
        "http://api.test",
        client=httpx.Client(
            base_url="http://api.test/",
            transport=httpx.MockTransport(handler),
        ),
    )

    client.review_notice(
        "notice-1",
        decision="modified",
        reviewer="Técnica",
        comment="Cambio sintético.",
        expected_version=0,
        category="incendio",
        urgency="critica",
        department="seguridad",
    )

    assert captured["category"] == "incendio"
    assert captured["urgency"] == "critica"
    assert captured["department"] == "seguridad"


def test_api_error_uses_only_safe_contract_message():
    def handler(request):
        return httpx.Response(
            503,
            json={
                "error": {
                    "code": "provider_unavailable",
                    "message": "El proveedor no está disponible temporalmente.",
                },
                "request_id": "request-1",
                "internal": "no se muestra",
            },
        )

    client = IAvisoApiClient(
        "http://api.test",
        client=httpx.Client(
            base_url="http://api.test/",
            transport=httpx.MockTransport(handler),
        ),
    )

    with pytest.raises(ApiClientError) as captured:
        client.create_triage(
            text="Caso sintético",
            provider="external",
            location=None,
        )

    assert str(captured.value) == "El proveedor no está disponible temporalmente."
    assert captured.value.code == "provider_unavailable"
    assert "internal" not in str(captured.value)


def test_connection_error_has_actionable_safe_message():
    def handler(request):
        raise httpx.ConnectError("host secreto", request=request)

    client = IAvisoApiClient(
        "http://api.test",
        client=httpx.Client(
            base_url="http://api.test/",
            transport=httpx.MockTransport(handler),
        ),
    )

    with pytest.raises(ApiClientError) as captured:
        client.list_notices()

    assert str(captured.value) == (
        "No se pudo conectar con la API. Comprueba que esté iniciada."
    )
    assert "host secreto" not in str(captured.value)
