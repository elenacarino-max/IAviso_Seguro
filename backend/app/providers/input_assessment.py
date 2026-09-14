"""Adaptadores Ollama/Gemini exclusivos de la comprobación de suficiencia."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from typing import Protocol
from urllib.parse import quote

import httpx

from backend.app.prompts.input_assessment import (
    build_gemini_input_assessment,
    build_ollama_input_assessment,
)
from backend.app.schemas.input_assessment import InputAssessmentRequest

from .base import ProviderOutput
from .errors import ProviderConnectionError, ProviderRateLimitError


class InputAssessmentProvider(Protocol):
    def assess(self, request: InputAssessmentRequest) -> ProviderOutput:
        """Analiza exclusivamente texto anonimizado."""
        ...


class InputAssessmentProviderRouter:
    """Selecciona de forma explícita el mismo proveedor elegido por el usuario."""

    def __init__(self, providers: Mapping[str, InputAssessmentProvider]) -> None:
        self._providers = dict(providers)

    def assess(self, request: InputAssessmentRequest) -> ProviderOutput:
        provider = self._providers.get(request.provider)
        if provider is None:
            raise ProviderConnectionError(
                "El proveedor de precheck solicitado no está configurado."
            )
        return provider.assess(request)


class OllamaInputAssessmentProvider:
    """Solicita JSON estructurado a `/api/chat` sin herramientas ni RAG."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_seconds: float,
        temperature: float,
        top_p: float,
        client: httpx.Client | None = None,
    ) -> None:
        if isinstance(timeout_seconds, bool) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds debe ser positivo.")
        if isinstance(temperature, bool) or not 0 <= temperature <= 2:
            raise ValueError("temperature debe estar entre 0 y 2.")
        if isinstance(top_p, bool) or not 0 < top_p <= 1:
            raise ValueError("top_p debe estar entre 0 y 1.")
        self._model = model.strip()
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/") + "/",
            timeout=timeout_seconds,
        )
        self._options = {"temperature": temperature, "top_p": top_p}

    def assess(self, request: InputAssessmentRequest) -> ProviderOutput:
        if not self._model:
            raise ProviderConnectionError("No hay un modelo local configurado.")
        body = build_ollama_input_assessment(request)
        body.update(
            {"model": self._model, "stream": False, "options": self._options}
        )
        try:
            response = self._client.post("api/chat", json=body)
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            raise ProviderConnectionError("No se pudo conectar con Ollama.") from exc
        if response.status_code == 429:
            raise ProviderRateLimitError(None)
        if response.is_error:
            raise ProviderConnectionError("Ollama rechazó el precheck.")
        try:
            payload = response.json()
        except (ValueError, UnicodeDecodeError) as exc:
            raise ProviderConnectionError("Ollama devolvió una respuesta ilegible.") from exc
        if not isinstance(payload, Mapping) or not isinstance(
            message := payload.get("message"), Mapping
        ):
            raise ProviderConnectionError("Ollama devolvió una respuesta incompleta.")
        content = message.get("content")
        if not isinstance(content, (str, bytes, Mapping)):
            raise ProviderConnectionError("Ollama no devolvió contenido utilizable.")
        return content


class GeminiInputAssessmentProvider:
    """Usa GenerateContent con JSON estricto y reintentos transitorios acotados."""

    _TRANSIENT = frozenset({408, 429, 500, 502, 503, 504})

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float,
        temperature: float,
        top_p: float,
        max_retries: int,
        retry_base_seconds: float,
        retry_max_seconds: float,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if isinstance(timeout_seconds, bool) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds debe ser positivo.")
        if isinstance(temperature, bool) or not 0 <= temperature <= 2:
            raise ValueError("temperature debe estar entre 0 y 2.")
        if isinstance(top_p, bool) or not 0 < top_p <= 1:
            raise ValueError("top_p debe estar entre 0 y 1.")
        if isinstance(max_retries, bool) or not 0 <= max_retries <= 5:
            raise ValueError("max_retries debe estar entre 0 y 5.")
        if not 0 <= retry_base_seconds <= retry_max_seconds:
            raise ValueError("La ventana de reintentos no es válida.")
        self._api_key = api_key.strip()
        self._model = model.strip()
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/") + "/",
            timeout=timeout_seconds,
        )
        self._temperature = temperature
        self._top_p = top_p
        self._max_retries = max_retries
        self._retry_base_seconds = retry_base_seconds
        self._retry_max_seconds = retry_max_seconds
        self._sleep = sleep

    def assess(self, request: InputAssessmentRequest) -> ProviderOutput:
        if not self._api_key:
            raise ProviderConnectionError("No hay una clave externa configurada.")
        if not self._model:
            raise ProviderConnectionError("No hay un modelo externo configurado.")
        body = build_gemini_input_assessment(request)
        generation = body["generationConfig"]
        assert isinstance(generation, dict)
        generation.update({"temperature": self._temperature, "topP": self._top_p})
        path = f"models/{quote(self._model, safe='')}:generateContent"
        response: httpx.Response | None = None
        for retry in range(self._max_retries + 1):
            try:
                response = self._client.post(
                    path,
                    headers={"x-goog-api-key": self._api_key},
                    json=body,
                )
            except (httpx.TimeoutException, httpx.RequestError) as exc:
                if retry == self._max_retries:
                    raise ProviderConnectionError(
                        "No se pudo conectar con Gemini."
                    ) from exc
                self._sleep(self._retry_delay(retry))
                continue
            if response.status_code in self._TRANSIENT and retry < self._max_retries:
                self._sleep(self._retry_delay(retry))
                continue
            break
        if response is None:
            raise ProviderConnectionError("Gemini no devolvió una respuesta.")
        if response.status_code == 429:
            raise ProviderRateLimitError(None)
        if response.is_error:
            raise ProviderConnectionError("Gemini rechazó el precheck.")
        try:
            payload = response.json()
        except (ValueError, UnicodeDecodeError) as exc:
            raise ProviderConnectionError("Gemini devolvió una respuesta ilegible.") from exc
        return self._content(payload)

    def _retry_delay(self, retry: int) -> float:
        return min(self._retry_base_seconds * (2**retry), self._retry_max_seconds)

    @staticmethod
    def _content(payload: object) -> str:
        if not isinstance(payload, Mapping):
            raise ProviderConnectionError("Gemini devolvió una respuesta incompleta.")
        candidates = payload.get("candidates")
        if not isinstance(candidates, list) or len(candidates) != 1:
            raise ProviderConnectionError("Gemini devolvió una respuesta incompleta.")
        candidate = candidates[0]
        if not isinstance(candidate, Mapping) or not isinstance(
            content := candidate.get("content"), Mapping
        ):
            raise ProviderConnectionError("Gemini devolvió una respuesta incompleta.")
        parts = content.get("parts")
        if not isinstance(parts, list):
            raise ProviderConnectionError("Gemini devolvió una respuesta incompleta.")
        texts = [part.get("text") for part in parts if isinstance(part, Mapping)]
        if not texts or any(not isinstance(text, str) for text in texts):
            raise ProviderConnectionError("Gemini no devolvió contenido utilizable.")
        return "".join(texts)
