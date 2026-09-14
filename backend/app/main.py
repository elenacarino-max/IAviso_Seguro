"""Punto de entrada de la API de IAviso Seguro."""

from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from backend.app.api.routes_catalogs import router as catalogs_router
from backend.app.api.routes_health import router as health_router
from backend.app.api.routes_knowledge import router as knowledge_router
from backend.app.api.routes_metrics import router as metrics_router
from backend.app.api.routes_precheck import router as precheck_router
from backend.app.api.routes_comparisons import router as comparisons_router
from backend.app.api.routes_evaluations import router as evaluations_router
from backend.app.api.routes_notices import router as notices_router
from backend.app.api.routes_risk_matrix import router as risk_matrix_router
from backend.app.api.routes_triage import router as triage_router
from backend.app.core.http_errors import register_exception_handlers
from backend.app.core.logging import configure_logging


def create_app() -> FastAPI:
    """Construye la aplicación para ejecución y pruebas aisladas."""

    application = FastAPI(
        title="IAviso Seguro",
        description="API académica de triaje asistido de riesgos laborales.",
        version="1.0.0",
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
    application.include_router(catalogs_router)
    application.include_router(metrics_router)
    application.include_router(precheck_router)
    application.include_router(triage_router)
    application.include_router(notices_router)
    application.include_router(comparisons_router)
    application.include_router(evaluations_router)
    application.include_router(risk_matrix_router)
    application.include_router(knowledge_router)

    frontend_dist = Path(__file__).resolve().parents[2] / "frontend-react" / "dist"
    if frontend_dist.is_dir():
        application.mount(
            "/",
            StaticFiles(directory=frontend_dist, html=True),
            name="dashboard",
        )
    return application


configure_logging()
app = create_app()
