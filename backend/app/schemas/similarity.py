"""Contratos de recurrencia semántica y embeddings persistidos."""

from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from .catalogs import Category, Urgency

EmbeddingModel = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]


class SimilarityContract(BaseModel):
    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        frozen=True,
        allow_inf_nan=False,
    )


class SimilarityMatch(SimilarityContract):
    """Aviso histórico próximo; score es coseno, no probabilidad."""

    notice_id: UUID
    score: float = Field(ge=0, le=1)
    same_location: bool
    location: str | None
    created_at: datetime
    category: Category
    urgency: Urgency


class SimilarityResult(SimilarityContract):
    """Señal complementaria que nunca decide si dos incidentes son iguales."""

    available: bool = False
    has_similar: bool = False
    match_count: int = Field(default=0, strict=True, ge=0)
    matches: tuple[SimilarityMatch, ...] = ()

    @model_validator(mode="after")
    def require_consistent_result(self) -> Self:
        if self.match_count != len(self.matches):
            raise ValueError("El recuento debe coincidir con los avisos devueltos.")
        if self.has_similar != (self.match_count > 0):
            raise ValueError("El indicador de recurrencia no coincide con el recuento.")
        if not self.available and self.match_count > 0:
            raise ValueError("Una detección no disponible no puede incluir avisos.")
        scores = [match.score for match in self.matches]
        if scores != sorted(scores, reverse=True):
            raise ValueError("Los avisos similares deben ordenarse por puntuación.")
        return self


class NoticeEmbedding(SimilarityContract):
    """Vector interno asociado a un aviso; nunca forma parte de la API pública."""

    model: EmbeddingModel
    dimensions: int = Field(strict=True, ge=1)
    vector: tuple[float, ...]

    @field_validator("vector")
    @classmethod
    def require_non_empty_vector(cls, value: tuple[float, ...]) -> tuple[float, ...]:
        if not value or all(component == 0 for component in value):
            raise ValueError("El embedding debe contener información utilizable.")
        return value

    @model_validator(mode="after")
    def dimensions_must_match(self) -> Self:
        if self.dimensions != len(self.vector):
            raise ValueError("Las dimensiones no coinciden con el vector.")
        return self


class StoredNoticeEmbedding(NoticeEmbedding):
    """Vector histórico enriquecido con datos operativos no sensibles."""

    notice_id: UUID
    location: str | None
    created_at: datetime
    category: Category
    urgency: Urgency
