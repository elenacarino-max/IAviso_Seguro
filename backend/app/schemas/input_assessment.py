"""Contratos estrictos de la comprobación previa de suficiencia."""

import re
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from .catalogs import Provider
from .privacy import PrivacyMetadata
from .triage import LocationText, NoticeText

MissingAspect = Literal["hazard", "exposure", "immediacy", "context"]
ClarifyingQuestion = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=5, max_length=200),
]

_SENSITIVE_QUESTION = re.compile(
    r"\b(?:nombre|apellidos?|dni|nie|tel[eé]fono|correo|e-?mail|edad|sexo|g[eé]nero|"
    r"nacionalidad|raza|barrio|direcci[oó]n|diagn[oó]stico|enfermedad|"
    r"historial\s+m[eé]dico|datos?\s+m[eé]dicos?|"
    r"origen\s+(?:[eé]tnico|nacional|de\s+la\s+persona|del\s+trabajador))\b",
    re.IGNORECASE,
)


class InputAssessmentContract(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class InputAssessmentRequest(InputAssessmentContract):
    """Misma entrada operativa, sin exigir ubicación para valorar el peligro."""

    text: NoticeText
    provider: Provider
    location: LocationText | None = None


class InputAssessmentDecision(InputAssessmentContract):
    """Decisión validada del proveedor; no contiene razonamiento interno."""

    sufficient: bool
    questions: tuple[ClarifyingQuestion, ...] = Field(max_length=3)
    missing_aspects: tuple[MissingAspect, ...] = Field(max_length=4)

    @field_validator("questions")
    @classmethod
    def questions_must_be_safe(
        cls,
        questions: tuple[str, ...],
    ) -> tuple[str, ...]:
        if len(set(questions)) != len(questions):
            raise ValueError("Las preguntas aclaratorias no pueden repetirse.")
        if any(_SENSITIVE_QUESTION.search(question) for question in questions):
            raise ValueError("Las preguntas no pueden solicitar datos sensibles.")
        return questions

    @field_validator("missing_aspects")
    @classmethod
    def missing_aspects_must_be_unique(
        cls,
        aspects: tuple[MissingAspect, ...],
    ) -> tuple[MissingAspect, ...]:
        if len(set(aspects)) != len(aspects):
            raise ValueError("Los aspectos ausentes no pueden repetirse.")
        return aspects

    @model_validator(mode="after")
    def decision_must_be_consistent(self) -> Self:
        if self.sufficient and (self.questions or self.missing_aspects):
            raise ValueError("Un aviso suficiente no necesita aclaraciones.")
        if not self.sufficient and (not self.questions or not self.missing_aspects):
            raise ValueError(
                "Un aviso insuficiente debe indicar preguntas y aspectos ausentes."
            )
        return self


class InputAssessmentResponse(InputAssessmentContract):
    """Respuesta pública capaz de representar un fallo técnico sin falsear éxito."""

    available: bool
    sufficient: bool | None
    questions: tuple[ClarifyingQuestion, ...] = Field(default=(), max_length=3)
    missing_aspects: tuple[MissingAspect, ...] = Field(default=(), max_length=4)
    privacy: PrivacyMetadata = Field(default_factory=PrivacyMetadata)

    @model_validator(mode="after")
    def response_must_be_consistent(self) -> Self:
        if not self.available:
            if self.sufficient is not None or self.questions or self.missing_aspects:
                raise ValueError("Un precheck no disponible no puede afirmar un resultado.")
            return self
        if self.sufficient is None:
            raise ValueError("Un precheck disponible debe indicar si el aviso es suficiente.")
        InputAssessmentDecision(
            sufficient=self.sufficient,
            questions=self.questions,
            missing_aspects=self.missing_aspects,
        )
        return self
