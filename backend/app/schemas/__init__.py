"""Contratos públicos de triaje."""

from .health import HealthResponse
from .errors import ErrorDetail, ErrorResponse
from .triage import TriageRequest, TriageResult

__all__ = ["ErrorDetail", "ErrorResponse", "HealthResponse", "TriageRequest", "TriageResult"]
