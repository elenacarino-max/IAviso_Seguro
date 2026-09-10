"""Punto de entrada de la API de IAviso Seguro."""

from uuid import uuid4

from fastapi import FastAPI, Request

from backend.app.api.routes_health import router as health_router
from backend.app.api.routes_comparisons import router as comparisons_router
from backend.app.api.routes_notices import router as notices_router
from backend.app.api.routes_triage import router as triage_router
from backend.app.core.http_errors import register_exception_handlers
from backend.app.core.logging import configure_logging


def create_app() -> FastAPI:
    """Construye la aplicación para ejecución y pruebas aisladas."""

    application = FastAPI(
        title="IAviso Seguro",
        description="API académica de triaje asistido de riesgos laborales.",
        version="0.7.0",
    )

    @application.middleware("http")
    async def add_request_id(request: Request, call_next):
        request_id = str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    register_exception_handlers(application)
    application.include_router(health_router)
    application.include_router(triage_router)
    application.include_router(notices_router)
    application.include_router(comparisons_router)
    return application


configure_logging()
app = create_app()
