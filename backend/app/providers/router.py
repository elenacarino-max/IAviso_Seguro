"""Selección explícita del adaptador solicitado por el contrato de entrada."""

from collections.abc import Mapping
from contextvars import ContextVar

from backend.app.schemas import RiskMatrixObservation, TriageRequest

from .base import (
    ProviderCallMetrics,
    ProviderStep,
    RepairContext,
    ToolCall,
    TriageProvider,
)
from .errors import ProviderConnectionError


class ProviderRouter:
    """Delega sin enviar avisos a un proveedor distinto del solicitado."""

    def __init__(self, providers: Mapping[str, TriageProvider]) -> None:
        self._providers = dict(providers)
        self._selected_provider: ContextVar[TriageProvider | None] = ContextVar(
            f"selected_provider_{id(self)}",
            default=None,
        )

    @property
    def last_call_metrics(self) -> ProviderCallMetrics | None:
        provider = self._selected_provider.get()
        value = getattr(provider, "last_call_metrics", None)
        return value if isinstance(value, ProviderCallMetrics) else None

    def generate(
        self,
        request: TriageRequest,
        *,
        observation: RiskMatrixObservation | None = None,
        repair: RepairContext | None = None,
        tool_call: ToolCall | None = None,
    ) -> ProviderStep:
        provider = self._providers.get(request.provider)
        if provider is None:
            raise ProviderConnectionError(
                "El proveedor solicitado todavía no está configurado."
            )
        self._selected_provider.set(provider)
        return provider.generate(
            request,
            observation=observation,
            repair=repair,
            tool_call=tool_call,
        )
