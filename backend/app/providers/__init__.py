"""Proveedores intercambiables utilizados por el servicio de triaje."""

from .base import ProviderOutput, RepairContext, TriageProvider
from .errors import ProviderConnectionError, ProviderError, ProviderRateLimitError
from .mock import MockTriageProvider

__all__ = [
    "MockTriageProvider",
    "ProviderConnectionError",
    "ProviderError",
    "ProviderOutput",
    "ProviderRateLimitError",
    "RepairContext",
    "TriageProvider",
]
