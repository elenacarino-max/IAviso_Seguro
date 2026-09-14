"""Contratos cerrados para incertidumbre y prioridad de revisión humana."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator, model_validator

UncertaintyLevel = Literal["low", "medium", "high"]
ReviewPriorityLevel = Literal["low", "medium", "high", "critical"]
NoticeOrder = Literal["newest", "review_priority"]
UncertaintyReason = Literal[
    "provider_output_repaired",
    "multiple_repairs",
    "generic_category",
    "incomplete_evidence",
    "provider_retry",
]
ReviewPriorityReason = Literal[
    "low_urgency",
    "medium_urgency",
    "high_urgency",
    "critical_urgency",
    "high_uncertainty",
    "recurrent_risk",
    "recurrent_same_location",
]
ReviewPolicyVersion = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^v[1-9]\d*$"),
]


class ReviewPolicyContract(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class UncertaintyAssessment(ReviewPolicyContract):
    """Señales técnicas observadas; el nivel no es una probabilidad."""

    level: UncertaintyLevel
    reasons: tuple[UncertaintyReason, ...] = ()

    @field_validator("reasons")
    @classmethod
    def reasons_must_be_unique(
        cls,
        reasons: tuple[UncertaintyReason, ...],
    ) -> tuple[UncertaintyReason, ...]:
        if len(reasons) != len(set(reasons)):
            raise ValueError("Las razones de incertidumbre deben ser únicas.")
        return reasons

    @model_validator(mode="after")
    def level_must_match_presence_of_signals(self) -> Self:
        if (self.level == "low") != (not self.reasons):
            raise ValueError(
                "La incertidumbre baja exige ausencia de señales y viceversa."
            )
        return self


class ReviewPriorityAssessment(ReviewPolicyContract):
    """Orden operativo recomendado, separado de urgencia e incertidumbre."""

    level: ReviewPriorityLevel
    reasons: tuple[ReviewPriorityReason, ...]

    @field_validator("reasons")
    @classmethod
    def reasons_must_be_unique_and_include_one_urgency(
        cls,
        reasons: tuple[ReviewPriorityReason, ...],
    ) -> tuple[ReviewPriorityReason, ...]:
        if len(reasons) != len(set(reasons)):
            raise ValueError("Las razones de prioridad deben ser únicas.")
        urgency_reasons = {
            "low_urgency",
            "medium_urgency",
            "high_urgency",
            "critical_urgency",
        }
        if sum(reason in urgency_reasons for reason in reasons) != 1:
            raise ValueError("La prioridad debe conservar exactamente una urgencia base.")
        return reasons
