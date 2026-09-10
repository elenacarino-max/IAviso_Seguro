"""Cliente HTTP seguro; el frontend no accede a datos ni modelos directamente."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

import httpx


class ApiClientError(RuntimeError):
    """Error presentable al usuario sin detalles internos ni stack traces."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code


class IAvisoApiClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 30,
        client: httpx.Client | None = None,
    ) -> None:
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/") + "/",
            timeout=timeout_seconds,
        )

    def create_triage(
        self,
        *,
        text: str,
        provider: str,
        location: str | None,
    ) -> dict[str, Any]:
        return self._mapping(
            self._request(
                "POST",
                "api/v1/triage",
                json={
                    "text": text,
                    "provider": provider,
                    "location": location,
                },
            )
        )

    def list_notices(self) -> list[dict[str, Any]]:
        value = self._request("GET", "api/v1/notices")
        if not isinstance(value, list) or not all(
            isinstance(item, Mapping) for item in value
        ):
            raise ApiClientError("La API devolvió una lista de avisos inválida.")
        return [dict(item) for item in value]

    def review_notice(
        self,
        notice_id: str | UUID,
        *,
        decision: str,
        reviewer: str,
        comment: str,
        expected_version: int,
        category: str | None = None,
        urgency: str | None = None,
        department: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "decision": decision,
            "reviewer": reviewer,
            "comment": comment,
            "expected_version": expected_version,
        }
        if decision == "modified":
            payload.update(
                {
                    "category": category,
                    "urgency": urgency,
                    "department": department,
                }
            )
        return self._mapping(
            self._request(
                "POST",
                f"api/v1/notices/{notice_id}/reviews",
                json=payload,
            )
        )

    def compare(
        self,
        *,
        text: str,
        location: str | None,
    ) -> dict[str, Any]:
        return self._mapping(
            self._request(
                "POST",
                "api/v1/comparisons",
                json={"text": text, "location": location},
            )
        )

    def close(self) -> None:
        self._client.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> object:
        try:
            response = self._client.request(method, path, **kwargs)
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            raise ApiClientError(
                "No se pudo conectar con la API. Comprueba que esté iniciada."
            ) from exc

        if response.is_error:
            message = "La API no pudo completar la operación."
            code = None
            try:
                payload = response.json()
            except (ValueError, UnicodeDecodeError):
                payload = None
            if isinstance(payload, Mapping):
                detail = payload.get("error")
                if isinstance(detail, Mapping):
                    safe_message = detail.get("message")
                    safe_code = detail.get("code")
                    if isinstance(safe_message, str):
                        message = safe_message
                    if isinstance(safe_code, str):
                        code = safe_code
                elif response.status_code == 422:
                    message = "Revisa los campos introducidos."
            raise ApiClientError(
                message,
                status_code=response.status_code,
                code=code,
            )

        try:
            return response.json()
        except (ValueError, UnicodeDecodeError) as exc:
            raise ApiClientError("La API devolvió una respuesta ilegible.") from exc

    @staticmethod
    def _mapping(value: object) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            raise ApiClientError("La API devolvió una respuesta inválida.")
        return dict(value)
