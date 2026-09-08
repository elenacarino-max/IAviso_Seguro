"""Proveedores intercambiables utilizados por el servicio de triaje."""

from .base import ProviderOutput, ProviderStep, RepairContext, ToolCall, TriageProvider
from .errors import ProviderConnectionError, ProviderError, ProviderRateLimitError
from .mock import MockTriageProvider
from .ollama import OllamaTriageProvider
from .router import ProviderRouter

__all__ = [
    "MockTriageProvider",
    "OllamaTriageProvider",
    "ProviderConnectionError",
    "ProviderError",
    "ProviderOutput",
    "ProviderStep",
    "ProviderRateLimitError",
    "ProviderRouter",
    "RepairContext",
    "ToolCall",
    "TriageProvider",
]
