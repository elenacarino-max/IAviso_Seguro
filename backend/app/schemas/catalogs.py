"""Vocabulario estable del MVP; no establece reglas de prioridad."""

from typing import Literal

Category = Literal[
    "riesgo_electrico",
    "caidas_obstaculos",
    "incendio",
    "maquinaria",
    "sustancias_peligrosas",
    "problemas_estructurales",
    "falta_epi",
    "ergonomia",
    "otros",
]
Urgency = Literal["baja", "media", "alta", "critica"]
Department = Literal["prevencion", "mantenimiento", "seguridad", "limpieza"]
Provider = Literal["local", "external"]
