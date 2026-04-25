from fastapi import APIRouter
import httpx
from typing import Optional, Tuple

from app.core.config import get_settings
from app.models.schemas import (
    HealthFilesInfo,
    HealthModelInfo,
    HealthResponse,
    HealthSessionInfo,
    VseLLMHealth,
)
from app.services.settings_service import SettingsService
from app.storage.runtime import session_store

router = APIRouter(tags=["health"])


def check_vsellm_reachable() -> Tuple[Optional[bool], Optional[str]]:
    settings = get_settings()
    if not settings.vsellm_api_key_configured:
        return None, None

    try:
        response = httpx.get(
            f"{settings.vsellm_base_url.rstrip('/')}/models",
            headers={"Authorization": f"Bearer {settings.vsellm_api_key.strip()}"},
            timeout=httpx.Timeout(timeout=10.0, connect=5.0),
        )
    except (httpx.RequestError, httpx.TimeoutException):
        return False, "Не удалось проверить доступность VseLLM API."

    if response.status_code >= 400:
        return False, f"VseLLM API вернул ошибку ({response.status_code})."
    return True, None


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    settings = get_settings()
    settings_service = SettingsService(settings)
    runtime_settings = settings_service.get_settings()
    vsellm_reachable, vsellm_error = check_vsellm_reachable()

    return HealthResponse(
        status="ok",
        version=settings.app_version,
        environment=settings.app_env,
        vsellm=VseLLMHealth(
            api_key_configured=settings.vsellm_api_key_configured,
            base_url=settings.vsellm_base_url,
            reachable=vsellm_reachable,
        ),
        model=HealthModelInfo(selected=runtime_settings.selected_model),
        files=HealthFilesInfo(enabled=True, status="готов"),
        session=HealthSessionInfo(enabled=True, active_sessions=session_store.active_sessions_count()),
        last_error=vsellm_error,
    )
