"""Contrato HTTP del proveedor local de embeddings."""

import httpx
import pytest

from backend.app.providers import EmbeddingProviderError, OllamaEmbeddingProvider


def provider(handler):
    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="http://ollama.test/",
    )
    return OllamaEmbeddingProvider(
        base_url="http://ollama.test",
        model="embed-test",
        timeout_seconds=2,
        client=client,
    )


def test_ollama_embedding_uses_configured_model_and_api_embed():
    def handler(request: httpx.Request):
        assert request.url.path == "/api/embed"
        assert request.read().decode() == (
            '{"model":"embed-test","input":"Aviso anonimizado"}'
        )
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2, 0.3]]})

    result = provider(handler).embed("Aviso anonimizado")

    assert result == (0.1, 0.2, 0.3)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"embeddings": []},
        {"embeddings": [[0, 0]]},
        {"embeddings": [[1, "invalid"]]},
        {"embeddings": [[None]]},
    ],
)
def test_ollama_embedding_rejects_invalid_vectors(payload):
    embedding_provider = provider(
        lambda request: httpx.Response(200, json=payload)
    )

    with pytest.raises(EmbeddingProviderError):
        embedding_provider.embed("Aviso")


def test_ollama_embedding_maps_http_failure_without_response_details():
    embedding_provider = provider(
        lambda request: httpx.Response(404, text="modelo privado inexistente")
    )

    with pytest.raises(EmbeddingProviderError) as caught:
        embedding_provider.embed("Aviso")

    assert "modelo privado inexistente" not in str(caught.value)


def test_ollama_embedding_rejects_non_finite_values():
    embedding_provider = provider(
        lambda request: httpx.Response(
            200,
            content=b'{"embeddings":[[1e999]]}',
            headers={"Content-Type": "application/json"},
        )
    )

    with pytest.raises(EmbeddingProviderError):
        embedding_provider.embed("Aviso")
