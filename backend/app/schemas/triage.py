"""Validación de los avisos y de la clasificación propuesta por un modelo."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from .catalogs import Category, Department, Provider, Urgency

NoticeText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
LocationText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
ExplanationText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
SummaryText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class StrictContract(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class TriageRequest(StrictContract):
    """Aviso recibido por la futura API; proveedor explícito para evitar envíos implícitos."""

    text: NoticeText
    provider: Provider
    location: LocationText | None = None


class TriageResult(StrictContract):
    """Propuesta pendiente de revisión; no representa una decisión aprobada."""

    category: Category
    urgency: Urgency
    summary: SummaryText
    department: Department
    justification: ExplanationText

    @field_validator("summary")
    @classmethod
    def require_ten_words(cls, value: str) -> str:
        words = value.split()
        if len(words) != 10:
            raise ValueError(
                "El resumen debe contener exactamente 10 palabras; "
                f"se recibieron {len(words)}."
            )
        if any(not any(char.isalnum() for char in word) for word in words):
            raise ValueError("Cada palabra debe contener al menos una letra o un número.")
        return " ".join(words)
