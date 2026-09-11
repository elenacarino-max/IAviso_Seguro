"""Consulta pública de la matriz didáctica usada por el triaje."""

from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.schemas import RiskMatrixDocument
from backend.app.tools import RiskMatrixTool

router = APIRouter(prefix="/api/v1", tags=["risk-matrix"])


@lru_cache
def get_risk_matrix_tool() -> RiskMatrixTool:
    """Comparte la matriz validada sin exponer acceso directo al archivo."""

    return RiskMatrixTool()


@router.get("/risk-matrix", response_model=RiskMatrixDocument)
def get_risk_matrix(
    tool: Annotated[RiskMatrixTool, Depends(get_risk_matrix_tool)],
) -> RiskMatrixDocument:
    """Devuelve reglas, evidencia y límites didácticos de la versión activa."""

    return tool.document()
