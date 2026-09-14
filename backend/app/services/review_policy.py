"""Política determinista y versionada de supervisión humana."""

from backend.app.schemas import (
    ExecutionMetrics,
    ReviewPriorityAssessment,
    SimilarityResult,
    TriageResult,
    UncertaintyAssessment,
    Urgency,
)

REVIEW_POLICY_VERSION = "v1"


class UncertaintyService:
    """Deriva incertidumbre solo de telemetría y evidencia observables."""

    def assess(
        self,
        proposal: TriageResult,
        metrics: ExecutionMetrics,
    ) -> UncertaintyAssessment:
        reasons = []
        if metrics.repair_attempts > 0:
            reasons.append("provider_output_repaired")
        if metrics.repair_attempts > 1:
            reasons.append("multiple_repairs")
        if proposal.category == "otros":
            reasons.append("generic_category")

        evidence_types = {item.source_type for item in metrics.evidence}
        if not {"risk_matrix", "preventive_document"}.issubset(evidence_types):
            reasons.append("incomplete_evidence")

        # Un triaje correcto necesita dos llamadas lógicas: herramienta y salida.
        # Cada reparación añade otra; cualquier exceso es un retry de transporte.
        expected_logical_attempts = 2 + metrics.repair_attempts
        if metrics.provider_attempts > expected_logical_attempts:
            reasons.append("provider_retry")

        if not reasons:
            level = "low"
        elif metrics.repair_attempts > 1 or len(reasons) > 1:
            level = "high"
        else:
            level = "medium"
        return UncertaintyAssessment(level=level, reasons=tuple(reasons))


class ReviewPriorityService:
    """Ordena la revisión sin confundirla con gravedad ni confianza."""

    _LEVELS = ("low", "medium", "high", "critical")

    def assess(
        self,
        urgency: Urgency,
        uncertainty: UncertaintyAssessment,
        similarity: SimilarityResult,
    ) -> ReviewPriorityAssessment:
        base_reason = {
            "baja": "low_urgency",
            "media": "medium_urgency",
            "alta": "high_urgency",
            "critica": "critical_urgency",
        }[urgency]
        level_index = {"baja": 0, "media": 1, "alta": 2, "critica": 3}[urgency]
        reasons = [base_reason]

        if uncertainty.level == "high":
            reasons.append("high_uncertainty")
            level_index = self._raise_with_high_cap(level_index)

        same_location = similarity.has_similar and any(
            match.same_location for match in similarity.matches
        )
        if same_location:
            reasons.append("recurrent_same_location")
            level_index = self._raise_with_high_cap(level_index)
        elif similarity.has_similar:
            # La recurrencia general queda visible, pero no altera el orden.
            reasons.append("recurrent_risk")

        return ReviewPriorityAssessment(
            level=self._LEVELS[level_index],
            reasons=tuple(reasons),
        )

    @staticmethod
    def _raise_with_high_cap(level_index: int) -> int:
        """Eleva un nivel sin fabricar prioridad crítica desde señales técnicas."""

        return min(max(level_index, 0) + 1, 2) if level_index < 3 else 3
