"""Orquestación mínima del triaje en la Fase 1."""

from backend.app.providers.base import TriageProvider
from backend.app.schemas import TriageRequest, TriageResult


class TriageService:
    """Valida la propuesta del proveedor antes de devolverla a la API."""

    def __init__(self, provider: TriageProvider) -> None:
        self._provider = provider

    def triage(self, request: TriageRequest) -> TriageResult:
        candidate = self._provider.generate(request)
        return TriageResult.model_validate(candidate)
