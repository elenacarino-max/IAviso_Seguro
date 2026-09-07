"""Proveedores intercambiables utilizados por el servicio de triaje."""

from .base import TriageProvider
from .mock import MockTriageProvider

__all__ = ["MockTriageProvider", "TriageProvider"]
