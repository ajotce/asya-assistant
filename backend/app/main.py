from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from app.api.routes_chat import router as chat_router
from app.api.routes_health import router as health_router
from app.api.routes_models import router as models_router
from app.api.routes_session import router as session_router
from app.api.routes_settings import router as settings_router
from app.api.routes_usage import router as usage_router
from app.core.config import get_settings
from app.core.logging import configure_logging


def _is_subpath(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def register_frontend_routes(app: FastAPI, dist_dir: Path) -> None:
    index_file = dist_dir / "index.html"
    if not index_file.is_file():
        return

    @app.get("/", include_in_schema=False)
    def serve_frontend_index() -> FileResponse:
        return FileResponse(index_file)

    @app.get("/{file_path:path}", include_in_schema=False)
    def serve_frontend_files(file_path: str) -> FileResponse:
        if file_path.startswith("api/") or file_path in {"api", "docs", "openapi.json", "redoc"}:
            raise HTTPException(status_code=404)

        requested = (dist_dir / file_path).resolve()
        if _is_subpath(requested, dist_dir) and requested.is_file():
            return FileResponse(requested)
        return FileResponse(index_file)


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
    app.include_router(usage_router, prefix="/api")
    if settings.app_env == "local" and settings.serve_frontend:
        register_frontend_routes(app=app, dist_dir=settings.frontend_dist_dir)
    return app


app = create_app()
