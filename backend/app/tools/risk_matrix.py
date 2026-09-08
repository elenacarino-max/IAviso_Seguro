"""Consulta real y validada de la matriz de riesgos versionada."""

from collections.abc import Mapping
from pathlib import Path

from pydantic import ValidationError

from backend.app.schemas.catalogs import Category
from backend.app.schemas.risk_matrix import (
    RiskMatrixDocument,
    RiskMatrixObservation,
    RiskMatrixQuery,
    RiskMatrixRule,
)

from .errors import InvalidRiskMatrixError, InvalidToolArgumentsError

DEFAULT_MATRIX_PATH = Path(__file__).resolve().parents[3] / "config" / "risk_matrix.v1.json"


class RiskMatrixTool:
    """Carga una matriz validada y expone una única consulta autorizada."""

    name = "consultar_matriz_riesgos"

    def __init__(self, matrix_path: Path = DEFAULT_MATRIX_PATH) -> None:
        self._matrix_path = matrix_path
        self._document: RiskMatrixDocument | None = None
        self._rules: dict[Category, RiskMatrixRule] = {}

    @staticmethod
    def _load(matrix_path: Path) -> RiskMatrixDocument:
        try:
            raw = matrix_path.read_text(encoding="utf-8")
            return RiskMatrixDocument.model_validate_json(raw)
        except (OSError, ValidationError) as exc:
            raise InvalidRiskMatrixError(
                "La matriz de riesgos no está disponible o es inválida."
            ) from exc

    def execute(self, arguments: Mapping[str, object]) -> RiskMatrixObservation:
        if self._document is None:
            self._document = self._load(self._matrix_path)
            self._rules = {rule.category: rule for rule in self._document.rules}

        try:
            query = RiskMatrixQuery.model_validate(arguments)
        except ValidationError as exc:
            raise InvalidToolArgumentsError(
                "Los argumentos de consultar_matriz_riesgos son inválidos."
            ) from exc

        rule = self._rules[query.category]
        return RiskMatrixObservation(
            tool_name=self.name,
            arguments=query,
            matrix_version=self._document.version,
            rule_id=rule.rule_id,
            conditions=rule.conditions,
            recommended_urgency=rule.recommended_urgency,
            department=rule.department,
            evidence=rule.evidence,
            disclaimer=self._document.disclaimer,
        )


def consultar_matriz_riesgos(
    category: object,
    *,
    matrix_path: Path = DEFAULT_MATRIX_PATH,
) -> RiskMatrixObservation:
    """Consulta pública con categoría validada y resultado tipado."""

    return RiskMatrixTool(matrix_path).execute({"category": category})
