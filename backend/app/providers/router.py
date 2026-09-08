"""Selección explícita del adaptador solicitado por el contrato de entrada."""

from collections.abc import Mapping

from backend.app.schemas import RiskMatrixObservation, TriageRequest

from .base import ProviderStep, RepairContext, TriageProvider
from .errors import ProviderConnectionError


class ProviderRouter:
    """Delega sin enviar avisos a un proveedor distinto del solicitado."""

    def __init__(self, providers: Mapping[str, TriageProvider]) -> None:
        self._providers = dict(providers)

    def generate(
        self,
        request: TriageRequest,
        *,
        observation: RiskMatrixObservation | None = None,
        repair: RepairContext | None = None,
    ) -> ProviderStep:
        provider = self._providers.get(request.provider)
        if provider is None:
            raise ProviderConnectionError(
                "El proveedor solicitado todavía no está configurado."
            )
        return provider.generate(request, observation=observation, repair=repair)
