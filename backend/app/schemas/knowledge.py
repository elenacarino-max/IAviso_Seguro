"""Contratos del corpus preventivo y de la evidencia recuperada."""

from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from .catalogs import Category

KnowledgeText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1200),
]
SourceId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^[A-Z0-9-]{4,40}$"),
]
KnowledgeVersion = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^[1-9]\d*\.\d+\.\d+$"),
]


class KnowledgeContract(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class KnowledgeDocument(KnowledgeContract):
    """Fragmento sintético recuperable para una o varias categorías."""

    source_id: SourceId
    title: KnowledgeText
    section: KnowledgeText
    categories: tuple[Category, ...]
    keywords: tuple[KnowledgeText, ...]
    content: KnowledgeText

    @field_validator("categories", "keywords")
    @classmethod
    def require_unique_values(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or len(value) != len(set(value)):
            raise ValueError("La lista debe contener valores únicos y no estar vacía.")
        return value


class KnowledgeBase(KnowledgeContract):
    """Corpus versionado que debe cubrir todo el catálogo de riesgos."""

    version: KnowledgeVersion
    disclaimer: KnowledgeText
    documents: tuple[KnowledgeDocument, ...]

    @model_validator(mode="after")
    def require_unique_sources_and_complete_catalog(self) -> Self:
        identifiers = [document.source_id for document in self.documents]
        if not identifiers or len(identifiers) != len(set(identifiers)):
            raise ValueError("Las fuentes del corpus deben ser únicas.")
        covered = {
            category
            for document in self.documents
            for category in document.categories
        }
        from typing import get_args

        if covered != set(get_args(Category)):
            raise ValueError("El corpus debe cubrir todas las categorías.")
        if "sintético" not in self.disclaimer.lower():
            raise ValueError("El corpus debe declarar su carácter sintético.")
        return self


class KnowledgeEvidence(KnowledgeContract):
    """Fuente elegida por el backend; nunca procede del JSON generado por el LLM."""

    source_id: SourceId
    title: KnowledgeText
    section: KnowledgeText
    category: Category
    excerpt: KnowledgeText
    source_type: Literal["risk_matrix", "preventive_document"]
    version: KnowledgeVersion
    score: float = Field(strict=True, ge=0)
