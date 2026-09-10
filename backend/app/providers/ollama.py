"""Adaptador HTTP síncrono para la API local de Ollama."""

import json
from collections.abc import Mapping

import httpx

from backend.app.prompts import build_ollama_messages
from backend.app.prompts.output_format import ollama_output_schema
from backend.app.prompts.tool_context import RISK_MATRIX_TOOL
from backend.app.schemas import RiskMatrixObservation, TriageRequest

from .base import ProviderStep, RepairContext, ToolCall
from .errors import ProviderConnectionError, ProviderRateLimitError


class OllamaTriageProvider:
    """Usa /api/chat sin streaming y deja la validación al servicio común."""

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

    def generate(
        self,
        request: TriageRequest,
        *,
        observation: RiskMatrixObservation | None = None,
        repair: RepairContext | None = None,
        tool_call: ToolCall | None = None,
    ) -> ProviderStep:
        if not self._model:
            raise ProviderConnectionError("No hay un modelo local configurado.")

        body: dict[str, object] = {
            "model": self._model,
            "messages": build_ollama_messages(
                request,
                observation=observation,
                repair=repair,
            ),
            "stream": False,
            "options": self._options,
        }
        if observation is None:
            body["tools"] = [RISK_MATRIX_TOOL]
        else:
            body["format"] = ollama_output_schema()

        message = self._post_chat(body)
        tool_call = self._parse_tool_call(message)
        if tool_call is not None:
            return tool_call
        content = message.get("content", "")
        return content if isinstance(content, (str, bytes, Mapping)) else ""

    def _post_chat(self, body: Mapping[str, object]) -> Mapping[str, object]:
        try:
            response = self._client.post("api/chat", json=body)
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            raise ProviderConnectionError("No se pudo conectar con Ollama.") from exc

        if response.status_code == 429:
            raise ProviderRateLimitError(self._retry_after(response))
        if response.is_error:
            raise ProviderConnectionError("Ollama devolvió un error HTTP.")
        try:
            payload = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise ProviderConnectionError("Ollama devolvió una respuesta ilegible.") from exc
        if not isinstance(payload, Mapping) or not isinstance(payload.get("message"), Mapping):
            raise ProviderConnectionError("Ollama devolvió una respuesta incompleta.")
        return payload["message"]

    @staticmethod
    def _retry_after(response: httpx.Response) -> int | None:
        value = response.headers.get("Retry-After")
        if value is None:
            return None
        try:
            seconds = int(value)
        except ValueError:
            return None
        return seconds if seconds >= 0 else None

    @staticmethod
    def _parse_tool_call(message: Mapping[str, object]) -> ToolCall | None:
        calls = message.get("tool_calls")
        if not isinstance(calls, list) or len(calls) != 1:
            return None
        call = calls[0]
        if not isinstance(call, Mapping) or not isinstance(call.get("function"), Mapping):
            return None
        function = call["function"]
        name = function.get("name")
        arguments = function.get("arguments")
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                return None
        if not isinstance(name, str) or not isinstance(arguments, Mapping):
            return None
        return ToolCall(name=name, arguments=arguments)
