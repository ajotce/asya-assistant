from fastapi import FastAPI

from app.api.routes_chat import router as chat_router
from app.api.routes_health import router as health_router
from app.api.routes_models import router as models_router
from app.api.routes_session import router as session_router
from app.api.routes_settings import router as settings_router
from app.core.config import get_settings
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Asya Backend",
        version=settings.app_version,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    app.include_router(health_router, prefix="/api")
    app.include_router(models_router, prefix="/api")
    app.include_router(settings_router, prefix="/api")
    app.include_router(session_router, prefix="/api")
    app.include_router(chat_router, prefix="/api")
    return app


app = create_app()
