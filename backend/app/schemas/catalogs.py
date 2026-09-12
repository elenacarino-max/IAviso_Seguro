"""Vocabulario estable y catálogo público del MVP."""

from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, model_validator

Category = Literal[
    "riesgo_electrico",
    "caidas_obstaculos",
    "incendio",
    "maquinaria",
    "sustancias_peligrosas",
    "problemas_estructurales",
    "falta_epi",
    "ergonomia",
    "otros",
]
Urgency = Literal["baja", "media", "alta", "critica"]
Department = Literal["prevencion", "mantenimiento", "seguridad", "limpieza"]
Provider = Literal["local", "external"]


class CatalogsResponse(BaseModel):
    """Valores cerrados compartidos con los controles del frontend."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    categories: tuple[Category, ...]
    urgencies: tuple[Urgency, ...]
    departments: tuple[Department, ...]

    @classmethod
    def current(cls) -> "CatalogsResponse":
        return cls(
            categories=get_args(Category),
            urgencies=get_args(Urgency),
            departments=get_args(Department),
        )

    @model_validator(mode="after")
    def require_complete_unique_catalogs(self):
        expected = (
            (self.categories, get_args(Category)),
            (self.urgencies, get_args(Urgency)),
            (self.departments, get_args(Department)),
        )
        if any(values != canonical for values, canonical in expected):
            raise ValueError("Los catálogos deben conservar el contrato canónico.")
        return self
