"""Contratos públicos de triaje."""

from .health import HealthResponse
from .triage import TriageRequest, TriageResult

__all__ = ["HealthResponse", "TriageRequest", "TriageResult"]
