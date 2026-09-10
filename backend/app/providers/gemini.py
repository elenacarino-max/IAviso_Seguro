"""Adaptador HTTP para Gemini con reintentos transitorios acotados."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from time import perf_counter
from urllib.parse import quote

import httpx

from backend.app.prompts import build_gemini_request
from backend.app.schemas import RiskMatrixObservation, TriageRequest

from .base import ProviderStep, RepairContext, ToolCall
from .errors import ProviderConnectionError, ProviderRateLimitError

_TRANSIENT_HTTP_STATUS = frozenset({408, 500, 502, 503, 504})
_logger = logging.getLogger("iaviso.provider")


@dataclass(frozen=True, slots=True)
class ProviderUsage:
    """Tokens comunicados por el proveedor; ausentes significa desconocidos."""

    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None


class GeminiTriageProvider:
    """Usa Gemini GenerateContent sin filtrar secretos ni detalles internos."""

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
        clock: Callable[[], float] = perf_counter,
    ) -> None:
        if isinstance(timeout_seconds, bool) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds debe ser positivo.")
        if isinstance(temperature, bool) or not 0 <= temperature <= 2:
            raise ValueError("temperature debe estar entre 0 y 2.")
        if isinstance(top_p, bool) or not 0 < top_p <= 1:
            raise ValueError("top_p debe estar entre 0 y 1.")
        if (
            isinstance(max_retries, bool)
            or not isinstance(max_retries, int)
            or not 0 <= max_retries <= 5
        ):
            raise ValueError("max_retries debe estar entre 0 y 5.")
        if isinstance(retry_base_seconds, bool) or not 0 <= retry_base_seconds <= 60:
            raise ValueError("retry_base_seconds debe estar entre 0 y 60.")
        if isinstance(retry_max_seconds, bool) or not 0 <= retry_max_seconds <= 300:
            raise ValueError("retry_max_seconds debe estar entre 0 y 300.")
        if retry_base_seconds > retry_max_seconds:
            raise ValueError("retry_base_seconds no puede superar retry_max_seconds.")

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
        self._clock = clock
        self._last_usage = ProviderUsage(None, None, None)

    @property
    def last_usage(self) -> ProviderUsage:
        """Expone solo métricas reales de la última respuesta aceptada por HTTP."""

        return self._last_usage

    def generate(
        self,
        request: TriageRequest,
        *,
        observation: RiskMatrixObservation | None = None,
        repair: RepairContext | None = None,
        tool_call: ToolCall | None = None,
    ) -> ProviderStep:
        self._last_usage = ProviderUsage(None, None, None)
        if not self._api_key:
            raise ProviderConnectionError("No hay una clave externa configurada.")
        if not self._model:
            raise ProviderConnectionError("No hay un modelo externo configurado.")
        if observation is not None and (
            tool_call is None or tool_call.provider_context is None
        ):
            raise ProviderConnectionError(
                "Falta el contexto de la llamada de herramienta de Gemini."
            )

        body = build_gemini_request(
            request,
            observation=observation,
            repair=repair,
            tool_call=tool_call,
            temperature=self._temperature,
            top_p=self._top_p,
        )
        payload = self._post_generate_content(body)
        content = self._response_content(payload)
        parts = self._response_parts(content)
        parsed_tool_call = self._parse_tool_call(parts, content)
        if parsed_tool_call is not None:
            return parsed_tool_call
        return "".join(
            text
            for part in parts
            if isinstance((text := part.get("text")), str)
        )

    def _post_generate_content(
        self,
        body: Mapping[str, object],
    ) -> Mapping[str, object]:
        path = f"models/{quote(self._model, safe='')}:generateContent"
        for retry_count in range(self._max_retries + 1):
            started_at = self._clock()
            try:
                response = self._client.post(
                    path,
                    headers={"x-goog-api-key": self._api_key},
                    json=body,
                )
            except (httpx.TimeoutException, httpx.RequestError) as exc:
                self._log_attempt(
                    retry_count=retry_count,
                    outcome="transient_transport_error",
                    started_at=started_at,
                )
                if retry_count == self._max_retries:
                    raise ProviderConnectionError(
                        "No se pudo conectar con Gemini."
                    ) from exc
                self._sleep(self._retry_delay(retry_count))
                continue

            retry_after = self._retry_after(response)
            if response.status_code == 429:
                self._log_attempt(
                    retry_count=retry_count,
                    outcome="rate_limited",
                    started_at=started_at,
                    status_code=response.status_code,
                    retry_after_seconds=retry_after,
                )
                if retry_count == self._max_retries:
                    raise ProviderRateLimitError(retry_after)
                self._sleep(self._retry_delay(retry_count, retry_after))
                continue

            if response.status_code in _TRANSIENT_HTTP_STATUS:
                self._log_attempt(
                    retry_count=retry_count,
                    outcome="transient_http_error",
                    started_at=started_at,
                    status_code=response.status_code,
                )
                if retry_count == self._max_retries:
                    raise ProviderConnectionError(
                        "Gemini agotó los reintentos transitorios."
                    )
                self._sleep(self._retry_delay(retry_count))
                continue

            if response.is_error:
                self._log_attempt(
                    retry_count=retry_count,
                    outcome="non_transient_http_error",
                    started_at=started_at,
                    status_code=response.status_code,
                )
                raise ProviderConnectionError("Gemini rechazó la petición.")

            try:
                payload = response.json()
            except (ValueError, UnicodeDecodeError) as exc:
                self._log_attempt(
                    retry_count=retry_count,
                    outcome="invalid_response",
                    started_at=started_at,
                    status_code=response.status_code,
                )
                raise ProviderConnectionError(
                    "Gemini devolvió una respuesta ilegible."
                ) from exc
            if not isinstance(payload, Mapping):
                raise ProviderConnectionError(
                    "Gemini devolvió una respuesta incompleta."
                )

            self._last_usage = self._parse_usage(payload.get("usageMetadata"))
            self._log_attempt(
                retry_count=retry_count,
                outcome="accepted",
                started_at=started_at,
                status_code=response.status_code,
                usage=self._last_usage,
            )
            return payload

        raise ProviderConnectionError("Gemini no devolvió una respuesta.")

    def _retry_delay(
        self,
        retry_count: int,
        retry_after_seconds: int | None = None,
    ) -> float:
        exponential = self._retry_base_seconds * (2**retry_count)
        requested = retry_after_seconds or 0
        return min(max(exponential, requested), self._retry_max_seconds)

    def _log_attempt(
        self,
        *,
        retry_count: int,
        outcome: str,
        started_at: float,
        status_code: int | None = None,
        retry_after_seconds: int | None = None,
        usage: ProviderUsage | None = None,
    ) -> None:
        extra: dict[str, object] = {
            "provider": "gemini",
            "model": self._model,
            "provider_attempt": retry_count + 1,
            "retry_count": retry_count,
            "outcome": outcome,
            "latency_ms": round((self._clock() - started_at) * 1000, 3),
        }
        if status_code is not None:
            extra["status_code"] = status_code
        if retry_after_seconds is not None:
            extra["retry_after_seconds"] = retry_after_seconds
        if usage is not None:
            extra.update(
                {
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "total_tokens": usage.total_tokens,
                }
            )
        _logger.info("provider_attempt", extra=extra)

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
    def _parse_usage(value: object) -> ProviderUsage:
        if not isinstance(value, Mapping):
            return ProviderUsage(None, None, None)

        def token_count(name: str) -> int | None:
            count = value.get(name)
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                return None
            return count

        return ProviderUsage(
            input_tokens=token_count("promptTokenCount"),
            output_tokens=token_count("candidatesTokenCount"),
            total_tokens=token_count("totalTokenCount"),
        )

    @staticmethod
    def _response_content(payload: Mapping[str, object]) -> Mapping[str, object] | None:
        candidates = payload.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            return None
        candidate = candidates[0]
        if not isinstance(candidate, Mapping):
            return None
        content = candidate.get("content")
        return content if isinstance(content, Mapping) else None

    @staticmethod
    def _response_parts(
        content: Mapping[str, object] | None,
    ) -> list[Mapping[str, object]]:
        if content is None:
            return []
        parts = content.get("parts")
        if not isinstance(parts, list):
            return []
        return [part for part in parts if isinstance(part, Mapping)]

    @staticmethod
    def _parse_tool_call(
        parts: list[Mapping[str, object]],
        content: Mapping[str, object] | None,
    ) -> ToolCall | None:
        calls = [
            call
            for part in parts
            if isinstance((call := part.get("functionCall")), Mapping)
        ]
        if len(calls) != 1:
            return None
        name = calls[0].get("name")
        arguments = calls[0].get("args")
        if not isinstance(name, str) or not isinstance(arguments, Mapping):
            return None
        return ToolCall(
            name=name,
            arguments=arguments,
            provider_context=dict(content) if content is not None else None,
        )
