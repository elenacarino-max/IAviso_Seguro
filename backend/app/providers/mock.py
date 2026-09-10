"""Proveedor determinista para completar el flujo HTTP sin usar un LLM."""

from backend.app.schemas import RiskMatrixObservation, TriageRequest

from .base import ProviderStep, RepairContext, ToolCall


class MockTriageProvider:
    """Devuelve una propuesta sintética y explícitamente no profesional."""

    def generate(
        self,
        request: TriageRequest,
        *,
        observation: RiskMatrixObservation | None = None,
        repair: RepairContext | None = None,
        tool_call: ToolCall | None = None,
    ) -> ProviderStep:
        if observation is None:
            return ToolCall(
                name="consultar_matriz_riesgos",
                arguments={"category": "otros"},
            )

        location = request.location or "ubicación no indicada"
        return {
            "category": observation.arguments.category,
            "urgency": observation.recommended_urgency,
            "summary": "Aviso recibido correctamente y preparado para revisión humana del técnico.",
            "department": observation.department,
            "justification": (
                f"Matriz didáctica {observation.matrix_version}, regla "
                f"{observation.rule_id}, para {location}: {observation.evidence} "
                "La propuesta requiere revisión profesional."
            ),
        }
