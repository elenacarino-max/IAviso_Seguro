"""Contrato mínimo que deben cumplir los proveedores de triaje."""

from collections.abc import Mapping
from typing import Protocol

from backend.app.schemas import TriageRequest


class TriageProvider(Protocol):
    """Permite sustituir el mock por proveedores reales sin cambiar el servicio."""

    def generate(self, request: TriageRequest) -> Mapping[str, object]:
        """Genera datos candidatos que todavía deben validarse."""
        ...
