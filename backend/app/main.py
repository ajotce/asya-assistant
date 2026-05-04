from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from app.api.routes_access_requests import admin_router as admin_access_requests_router
from app.api.routes_access_requests import public_router as access_requests_router
from app.api.routes_action_rollback import router as action_rollback_router
from app.api.routes_auth import router as auth_router
from app.api.routes_briefings import router as briefings_router
from app.api.routes_chats import router as chats_router
from app.api.routes_diary import router as diary_router
from app.api.routes_document_templates import router as document_templates_router
from app.api.routes_documents import router as documents_router
from app.api.routes_chat import router as chat_router
from app.api.routes_health import router as health_router
from app.api.routes_integrations import router as integrations_router
from app.api.routes_models import router as models_router
from app.api.routes_memory import router as memory_router
from app.api.routes_observer import router as observer_router
from app.api.routes_session import router as session_router
from app.api.routes_settings import router as settings_router
from app.api.routes_storage import router as storage_router
from app.api.routes_spaces import router as spaces_router
from app.api.routes_telegram import router as telegram_router
from app.api.routes_usage import router as usage_router
from app.api.routes_voice import router as voice_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.services.scheduler_service import start_scheduler, stop_scheduler


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
    app.include_router(auth_router, prefix="/api")
    app.include_router(access_requests_router, prefix="/api")
    app.include_router(admin_access_requests_router, prefix="/api")
    app.include_router(models_router, prefix="/api")
    app.include_router(settings_router, prefix="/api")
    app.include_router(storage_router, prefix="/api")
    app.include_router(session_router, prefix="/api")
    app.include_router(chats_router, prefix="/api")
    app.include_router(briefings_router, prefix="/api")
    app.include_router(diary_router, prefix="/api")
    app.include_router(document_templates_router, prefix="/api")
    app.include_router(documents_router, prefix="/api")
    app.include_router(spaces_router, prefix="/api")
    app.include_router(memory_router, prefix="/api")
    app.include_router(action_rollback_router, prefix="/api")
    app.include_router(observer_router, prefix="/api")
    app.include_router(integrations_router, prefix="/api")
    app.include_router(telegram_router, prefix="/api")
    app.include_router(voice_router, prefix="/api")
    app.include_router(chat_router, prefix="/api")
    app.include_router(usage_router, prefix="/api")
    if settings.app_env == "local" and settings.serve_frontend:
        register_frontend_routes(app=app, dist_dir=settings.frontend_dist_dir)

    @app.on_event("startup")
    def _startup_scheduler() -> None:
        start_scheduler()

    @app.on_event("shutdown")
    def _shutdown_scheduler() -> None:
        stop_scheduler()

    return app


app = create_app()
