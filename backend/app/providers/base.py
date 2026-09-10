"""Contrato mínimo que deben cumplir los proveedores de triaje."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from backend.app.schemas import RiskMatrixObservation, TriageRequest

ProviderOutput = str | bytes | Mapping[str, object]

@dataclass(frozen=True, slots=True)
class ToolCall:
    """Solicitud estructurada; el servicio decide si puede ejecutarse."""

    name: str
    arguments: Mapping[str, object]
    provider_context: Mapping[str, object] | None = field(
        default=None, compare=False, repr=False
    )


ProviderStep = ProviderOutput | ToolCall



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
        observation: RiskMatrixObservation | None = None,
        repair: RepairContext | None = None,
        tool_call: ToolCall | None = None,
    ) -> ProviderStep:
        """Solicita una herramienta o genera una salida candidata."""
        ...
