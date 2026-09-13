"""Adaptador local para embeddings de Ollama sin descarga de modelos."""

import json
import math
from collections.abc import Mapping, Sequence

import httpx

from .errors import EmbeddingProviderError


class OllamaEmbeddingProvider:
    """Usa `/api/embed`; el modelo debe existir previamente en Ollama."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_seconds: float,
        client: httpx.Client | None = None,
    ) -> None:
        if isinstance(timeout_seconds, bool) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds debe ser positivo.")
        self._model = model.strip()
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/") + "/",
            timeout=timeout_seconds,
        )

    def embed(self, text: str) -> tuple[float, ...]:
        if not self._model:
            raise EmbeddingProviderError("No hay un modelo de embeddings configurado.")
        try:
            response = self._client.post(
                "api/embed",
                json={"model": self._model, "input": text},
            )
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            raise EmbeddingProviderError(
                "No se pudo conectar con Ollama para generar el embedding."
            ) from exc
        if response.is_error:
            raise EmbeddingProviderError("Ollama rechazó la solicitud de embedding.")
        try:
            payload = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise EmbeddingProviderError(
                "Ollama devolvió un embedding ilegible."
            ) from exc
        return self._parse_vector(payload)

    @staticmethod
    def _parse_vector(payload: object) -> tuple[float, ...]:
        if not isinstance(payload, Mapping):
            raise EmbeddingProviderError("La respuesta de embeddings es inválida.")
        embeddings = payload.get("embeddings")
        if (
            not isinstance(embeddings, Sequence)
            or isinstance(embeddings, (str, bytes))
            or len(embeddings) != 1
        ):
            raise EmbeddingProviderError("La respuesta no contiene un único embedding.")
        raw_vector = embeddings[0]
        if not isinstance(raw_vector, Sequence) or isinstance(raw_vector, (str, bytes)):
            raise EmbeddingProviderError("El vector devuelto es inválido.")
        vector: list[float] = []
        for component in raw_vector:
            if isinstance(component, bool) or not isinstance(component, (int, float)):
                raise EmbeddingProviderError("El vector contiene valores inválidos.")
            value = float(component)
            if not math.isfinite(value):
                raise EmbeddingProviderError("El vector contiene valores no finitos.")
            vector.append(value)
        if not vector or all(component == 0 for component in vector):
            raise EmbeddingProviderError("El vector devuelto no es utilizable.")
        return tuple(vector)
