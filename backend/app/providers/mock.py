"""Proveedor determinista para completar el flujo HTTP sin usar un LLM."""

from collections.abc import Mapping

from backend.app.schemas import TriageRequest


class MockTriageProvider:
    """Devuelve una propuesta sintética y explícitamente no profesional."""

    def generate(self, request: TriageRequest) -> Mapping[str, object]:
        location = request.location or "ubicación no indicada"
        return {
            "category": "otros",
            "urgency": "media",
            "summary": "Aviso recibido correctamente y preparado para revisión humana del técnico.",
            "department": "prevencion",
            "justification": (
                "Respuesta simulada de la Fase 1 para "
                f"{location}; todavía no procede de un modelo real."
            ),
        }
