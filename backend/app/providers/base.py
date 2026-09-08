"""Contrato mínimo que deben cumplir los proveedores de triaje."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from backend.app.schemas import TriageRequest

ProviderOutput = str | bytes | Mapping[str, object]


@dataclass(frozen=True, slots=True)
class RepairContext:
    """Información acotada para pedir al proveedor que corrija su salida."""

    invalid_output: ProviderOutput
    validation_errors: tuple[str, ...]


class TriageProvider(Protocol):
    """Permite sustituir el mock por proveedores reales sin cambiar el servicio."""

    def generate(
        self,
        request: TriageRequest,
        *,
        repair: RepairContext | None = None,
    ) -> ProviderOutput:
        """Genera una salida inicial o corrige una salida previamente rechazada."""
        ...
