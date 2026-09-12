"""Catálogos cerrados usados por la API y los formularios."""

from fastapi import APIRouter

from backend.app.schemas import CatalogsResponse

router = APIRouter(prefix="/api/v1", tags=["catalogs"])


@router.get("/catalogs", response_model=CatalogsResponse)
def get_catalogs() -> CatalogsResponse:
    """Publica exactamente los valores aceptados por Pydantic."""

    return CatalogsResponse.current()
