from pathlib import Path
import time
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from sentry_sdk import init as sentry_init
from sentry_sdk.integrations.fastapi import FastApiIntegration
from starlette.requests import Request

from app.api.routes_access_requests import admin_router as admin_access_requests_router
from app.api.routes_access_requests import public_router as access_requests_router
from app.api.routes_auth import router as auth_router
from app.api.routes_chats import router as chats_router
from app.api.routes_diary import router as diary_router
from app.api.routes_chat import router as chat_router
from app.api.routes_health import router as health_router
from app.api.routes_integrations import router as integrations_router
from app.api.routes_models import router as models_router
from app.api.routes_memory import router as memory_router
from app.api.routes_me import router as me_router
from app.api.routes_observer import router as observer_router
from app.api.routes_session import router as session_router
from app.api.routes_settings import router as settings_router
from app.api.routes_spaces import router as spaces_router
from app.api.routes_telegram import router as telegram_router
from app.api.routes_usage import router as usage_router
from app.api.routes_voice import router as voice_router
from app.core.config import Settings
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.request_context import request_id_ctx
from app.observability.metrics import sanitize_sentry_payload, setup_metrics
from app.services.scheduler_service import start_scheduler, stop_scheduler


def _setup_sentry(settings: Settings) -> None:
    dsn = settings.sentry_dsn.strip()
    if not dsn:
        return

    def _before_send(event, hint):
        _ = hint
        request_payload = event.get("request")
        if isinstance(request_payload, dict):
            request_payload.pop("data", None)
            request_payload.pop("cookies", None)
            headers = request_payload.get("headers")
            if isinstance(headers, dict):
                request_payload["headers"] = sanitize_sentry_payload(headers)
            event["request"] = request_payload
        return sanitize_sentry_payload(event)

    sentry_init(
        dsn=dsn,
        environment=settings.app_env,
        release=f"asya-backend@{settings.app_version}",
        traces_sample_rate=settings.sentry_traces_sample_rate,
        profiles_sample_rate=settings.sentry_profiles_sample_rate,
        integrations=[FastApiIntegration()],
        before_send=_before_send,
        send_default_pii=False,
    )


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
    configure_logging(settings.log_level, settings.log_format)
    _setup_sentry(settings)

    app = FastAPI(
        title="Asya Backend",
        version=settings.app_version,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    app.include_router(health_router, prefix="/api")
    app.include_router(health_router)
    app.include_router(auth_router, prefix="/api")
    app.include_router(access_requests_router, prefix="/api")
    app.include_router(admin_access_requests_router, prefix="/api")
    app.include_router(models_router, prefix="/api")
    app.include_router(settings_router, prefix="/api")
    app.include_router(session_router, prefix="/api")
    app.include_router(chats_router, prefix="/api")
    app.include_router(diary_router, prefix="/api")
    app.include_router(spaces_router, prefix="/api")
    app.include_router(memory_router, prefix="/api")
    app.include_router(me_router, prefix="/api")
    app.include_router(observer_router, prefix="/api")
    app.include_router(integrations_router, prefix="/api")
    app.include_router(telegram_router, prefix="/api")
    app.include_router(voice_router, prefix="/api")
    app.include_router(chat_router, prefix="/api")
    app.include_router(usage_router, prefix="/api")
    setup_metrics(app, settings)
    if settings.app_env == "local" and settings.serve_frontend:
        register_frontend_routes(app=app, dist_dir=settings.frontend_dist_dir)

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_ctx.set(request_id)
        started_at = time.perf_counter()
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{(time.perf_counter() - started_at):.6f}"
            return response
        finally:
            request_id_ctx.reset(token)

    if settings.enable_test_routes:
        @app.get("/api/test/sentry")
        def raise_test_sentry_exception() -> None:
            raise RuntimeError("Sentry test exception")

    @app.on_event("startup")
    def _startup_scheduler() -> None:
        start_scheduler()

    @app.on_event("shutdown")
    def _shutdown_scheduler() -> None:
        stop_scheduler()

    return app


app = create_app()
