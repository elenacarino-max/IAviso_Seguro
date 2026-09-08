"""Contratos estrictos de la matriz didáctica y su observación."""

from typing import Annotated, Literal, get_args

from pydantic import (
    BaseModel,
    ConfigDict,
    StringConstraints,
    field_validator,
    model_validator,
)

from .catalogs import Category, Department, Urgency

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
MatrixVersion = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^[1-9]\d*\.\d+\.\d+$"),
]
RuleId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^RM-[A-Z]{3,4}-\d{3}$"),
]


class MatrixContract(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class RiskMatrixQuery(MatrixContract):
    category: Category


class RiskMatrixRule(MatrixContract):
    rule_id: RuleId
    category: Category
    conditions: tuple[ShortText, ...]
    recommended_urgency: Urgency
    department: Department
    evidence: ShortText

    @field_validator("conditions")
    @classmethod
    def require_conditions(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("Cada regla debe incluir al menos una condición.")
        if len(set(value)) != len(value):
            raise ValueError("Las condiciones de una regla no pueden repetirse.")
        return value


class RiskMatrixDocument(MatrixContract):
    version: MatrixVersion
    disclaimer: ShortText
    rules: tuple[RiskMatrixRule, ...]

    @model_validator(mode="after")
    def require_complete_unique_catalog(self):
        expected = set(get_args(Category))
        categories = [rule.category for rule in self.rules]
        if set(categories) != expected or len(categories) != len(expected):
            raise ValueError("La matriz debe contener exactamente una regla por categoría.")
        rule_ids = [rule.rule_id for rule in self.rules]
        if len(set(rule_ids)) != len(rule_ids):
            raise ValueError("Los identificadores de regla deben ser únicos.")
        if "no es normativa" not in self.disclaimer.lower():
            raise ValueError("La matriz debe indicar expresamente que no es normativa.")
        return self


class RiskMatrixObservation(MatrixContract):
    tool_name: Literal["consultar_matriz_riesgos"]
    arguments: RiskMatrixQuery
    matrix_version: MatrixVersion
    rule_id: RuleId
    conditions: tuple[ShortText, ...]
    recommended_urgency: Urgency
    department: Department
    evidence: ShortText
    disclaimer: ShortText
