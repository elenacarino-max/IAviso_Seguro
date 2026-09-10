"""Evaluación reproducible sobre casos sintéticos separados del prompt."""

from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from backend.app.schemas import (
    EvaluationCase,
    EvaluationDataset,
    EvaluationObservation,
    EvaluationReport,
    ProviderEvaluationSummary,
    TriageRequest,
)

from .metrics import MetricsService
from .triage_service import TriageService

_DISCLAIMER = (
    "Resultados académicos sobre datos sintéticos; no son una referencia "
    "profesional ni sustituyen una evaluación preventiva."
)


def load_evaluation_dataset(path: str | Path) -> EvaluationDataset:
    return EvaluationDataset.model_validate_json(
        Path(path).read_text(encoding="utf-8")
    )


class EvaluationService:
    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))

    def run(
        self,
        dataset: EvaluationDataset,
        triage_service: TriageService,
        metrics_service: MetricsService,
    ) -> EvaluationReport:
        """Ejecuta cada caso una vez por proveedor sin persistir avisos."""

        observations: list[EvaluationObservation] = []
        for case in dataset.cases:
            for provider in ("local", "external"):
                request = TriageRequest(
                    text=case.text,
                    location=case.location,
                    provider=provider,
                )
                execution = triage_service.execute(
                    request,
                    request_id=f"evaluation:{dataset.version}:{case.id}:{provider}",
                )
                observations.append(
                    EvaluationObservation(
                        case_id=case.id,
                        provider=provider,
                        result=execution.result,
                        metrics=metrics_service.build(
                            request,
                            execution.telemetry,
                        ),
                    )
                )
        return self.summarize(dataset, observations)

    def summarize(
        self,
        dataset: EvaluationDataset,
        observations: Iterable[EvaluationObservation],
    ) -> EvaluationReport:
        expected = {case.id: case for case in dataset.cases}
        grouped: dict[str, list[EvaluationObservation]] = {
            "local": [],
            "external": [],
        }
        seen: set[tuple[str, str]] = set()
        for observation in observations:
            if observation.case_id not in expected:
                raise ValueError(
                    f"El caso observado no existe en el dataset: {observation.case_id}"
                )
            key = (observation.provider, observation.case_id)
            if key in seen:
                raise ValueError(
                    "Cada proveedor solo puede observar una vez el mismo caso."
                )
            seen.add(key)
            grouped[observation.provider].append(observation)

        summaries = tuple(
            self._provider_summary(provider, items, expected)
            for provider, items in grouped.items()
        )
        generated_at = self._clock()
        if generated_at.tzinfo is None or generated_at.utcoffset() is None:
            raise ValueError("El reloj de evaluación debe devolver una fecha con zona.")
        return EvaluationReport(
            dataset_version=dataset.version,
            generated_at=generated_at.astimezone(UTC),
            disclaimer=dataset.disclaimer or _DISCLAIMER,
            summaries=summaries,
        )

    @staticmethod
    def _provider_summary(
        provider: str,
        observations: list[EvaluationObservation],
        expected: dict[str, EvaluationCase],
    ) -> ProviderEvaluationSummary:
        count = len(observations)
        if not count:
            return ProviderEvaluationSummary(
                provider=provider,
                cases=0,
                api_cost_currency=None,
                reviewed_notices=0,
            )

        def accuracy(field: str) -> float:
            hits = 0
            for item in observations:
                case = expected[item.case_id]
                result = item.result
                if result is not None and getattr(result, field) == getattr(
                    case, f"expected_{field}"
                ):
                    hits += 1
            return hits / count

        json_values = [item.metrics.json_valid for item in observations]
        json_rate = (
            sum(value is True for value in json_values) / count
            if all(value is not None for value in json_values)
            else None
        )
        costs = [item.metrics.api_cost for item in observations]
        currencies = {item.metrics.api_cost_currency for item in observations}
        mean_cost: Decimal | None = None
        currency: str | None = None
        if all(value is not None for value in costs) and len(currencies) == 1:
            mean_cost = sum(
                (value for value in costs if value is not None),
                Decimal(0),
            ) / Decimal(count)
            currency = next(iter(currencies))

        reviewed = [
            item for item in observations if item.review_decision is not None
        ]
        correction_rate = (
            sum(
                item.review_decision in {"modified", "rejected"}
                for item in reviewed
            )
            / len(reviewed)
            if reviewed
            else None
        )
        return ProviderEvaluationSummary(
            provider=provider,
            cases=count,
            category_accuracy=accuracy("category"),
            urgency_accuracy=accuracy("urgency"),
            department_accuracy=accuracy("department"),
            json_valid_rate=json_rate,
            mean_latency_ms=(
                sum(item.metrics.latency_ms for item in observations) / count
            ),
            mean_api_cost=mean_cost,
            api_cost_currency=currency,
            reviewed_notices=len(reviewed),
            human_correction_rate=correction_rate,
        )
