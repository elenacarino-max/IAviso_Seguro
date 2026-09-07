"""Punto de entrada de la API de IAviso Seguro."""

from fastapi import FastAPI

from backend.app.api.routes_health import router as health_router
from backend.app.api.routes_triage import router as triage_router


def create_app() -> FastAPI:
    """Construye la aplicación para ejecución y pruebas aisladas."""

    application = FastAPI(
        title="IAviso Seguro",
        description="API académica de triaje asistido de riesgos laborales.",
        version="0.1.0",
    )
    application.include_router(health_router)
    application.include_router(triage_router)
    return application


app = create_app()
