"""Benchmark reproducible de calidad, latencia y coste por proveedor."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.schemas import EvaluationDataset, EvaluationReport
from backend.app.services import (
    EvaluationService,
    MetricsService,
    TriageService,
    load_evaluation_dataset,
)

from .routes_triage import get_metrics_service, get_triage_service

router = APIRouter(prefix="/api/v1", tags=["evaluations"])
_DATASET_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "evaluation"
    / "avisos.v1.json"
)


@lru_cache
def get_evaluation_dataset() -> EvaluationDataset:
    """Carga una única versión validada del benchmark sintético."""

    return load_evaluation_dataset(_DATASET_PATH)


def get_evaluation_service() -> EvaluationService:
    """Dependencia sustituible para mantener el endpoint comprobable."""

    return EvaluationService()


@router.post(
    "/evaluations",
    response_model=EvaluationReport,
    summary="Ejecutar el benchmark sintético con ambos proveedores",
    description=(
        "Ejecuta cada caso etiquetado una vez con Ollama y una vez con Gemini. "
        "No crea avisos ni decisiones operativas."
    ),
)
def create_evaluation(
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
    dataset: Annotated[EvaluationDataset, Depends(get_evaluation_dataset)],
    triage_service: Annotated[TriageService, Depends(get_triage_service)],
    metrics_service: Annotated[MetricsService, Depends(get_metrics_service)],
) -> EvaluationReport:
    return service.run(dataset, triage_service, metrics_service)
