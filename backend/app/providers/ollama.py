"""Adaptador HTTP síncrono para la API local de Ollama."""

import json
from collections.abc import Callable, Mapping
from contextvars import ContextVar
from time import perf_counter

import httpx

from backend.app.prompts import build_ollama_messages
from backend.app.prompts.output_format import ollama_output_schema
from backend.app.prompts.tool_context import RISK_MATRIX_TOOL
from backend.app.schemas import RiskMatrixObservation, TriageRequest

from .base import ProviderCallMetrics, ProviderStep, RepairContext, ToolCall
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
        clock: Callable[[], float] = perf_counter,
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
        self._clock = clock
        self._last_call: ContextVar[ProviderCallMetrics | None] = ContextVar(
            f"ollama_call_metrics_{id(self)}",
            default=None,
        )

    @property
    def last_call_metrics(self) -> ProviderCallMetrics | None:
        return self._last_call.get()

    def generate(
        self,
        request: TriageRequest,
        *,
        observation: RiskMatrixObservation | None = None,
        repair: RepairContext | None = None,
        tool_call: ToolCall | None = None,
    ) -> ProviderStep:
        self._last_call.set(None)
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
        started_at = self._clock()
        try:
            response = self._client.post("api/chat", json=body)
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            self._record_call(started_at, success=False, error_type="transport_error")
            raise ProviderConnectionError("No se pudo conectar con Ollama.") from exc

        if response.status_code == 429:
            self._record_call(
                started_at,
                success=False,
                error_type="rate_limited",
                status_code=429,
            )
            raise ProviderRateLimitError(self._retry_after(response))
        if response.is_error:
            self._record_call(
                started_at,
                success=False,
                error_type="http_error",
                status_code=response.status_code,
            )
            raise ProviderConnectionError("Ollama devolvió un error HTTP.")
        try:
            payload = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            self._record_call(
                started_at,
                success=False,
                error_type="invalid_response",
                status_code=response.status_code,
            )
            raise ProviderConnectionError("Ollama devolvió una respuesta ilegible.") from exc
        if not isinstance(payload, Mapping) or not isinstance(payload.get("message"), Mapping):
            self._record_call(
                started_at,
                success=False,
                error_type="incomplete_response",
                status_code=response.status_code,
            )
            raise ProviderConnectionError("Ollama devolvió una respuesta incompleta.")
        input_tokens = self._token_count(payload.get("prompt_eval_count"))
        output_tokens = self._token_count(payload.get("eval_count"))
        total_tokens = (
            input_tokens + output_tokens
            if input_tokens is not None and output_tokens is not None
            else None
        )
        self._record_call(
            started_at,
            success=True,
            status_code=response.status_code,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )
        return payload["message"]

    def _record_call(
        self,
        started_at: float,
        *,
        success: bool,
        error_type: str | None = None,
        status_code: int | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
    ) -> None:
        self._last_call.set(
            ProviderCallMetrics(
                provider_attempts=1,
                latency_ms=round((self._clock() - started_at) * 1000, 3),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                success=success,
                error_type=error_type,
                status_code=status_code,
            )
        )

    @staticmethod
    def _token_count(value: object) -> int | None:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return None
        return value

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
