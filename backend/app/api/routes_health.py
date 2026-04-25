import os
import time
from pathlib import Path
from typing import Optional, Tuple

from fastapi import APIRouter
import httpx

from app.core.config import get_settings
from app.models.schemas import (
    HealthEmbeddingsInfo,
    HealthFilesInfo,
    HealthModelInfo,
    HealthResponse,
    HealthSessionInfo,
    HealthStorageInfo,
    VseLLMHealth,
)
from app.services.settings_service import SettingsService
from app.storage.runtime import session_store

router = APIRouter(tags=["health"])
_START_TIME_MONOTONIC = time.monotonic()


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


def get_embeddings_status(
    embedding_model: str,
    api_key_configured: bool,
    vsellm_reachable: Optional[bool],
    vsellm_error: Optional[str],
) -> Tuple[str, Optional[str]]:
    if not embedding_model.strip():
        return "не настроен", "Embedding-модель не настроена."
    if not api_key_configured:
        return "не настроен", "VseLLM API-ключ не настроен."
    if vsellm_reachable is False:
        return "ошибка", vsellm_error or "VseLLM API недоступен."
    return "готов", None


def get_storage_status(tmp_dir: str) -> HealthStorageInfo:
    tmp_path = Path(tmp_dir).resolve()
    try:
        tmp_path.mkdir(parents=True, exist_ok=True)
        writable = os.access(tmp_path, os.W_OK)
    except OSError:
        writable = False

    if writable:
        session_store_status = "готов"
        file_store_status = "готов"
    else:
        session_store_status = "ошибка"
        file_store_status = "ошибка"

    return HealthStorageInfo(
        session_store=session_store_status,
        file_store=file_store_status,
        tmp_dir=str(tmp_path),
        writable=writable,
    )


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    settings = get_settings()
    settings_service = SettingsService(settings)
    runtime_settings = settings_service.get_settings()
    vsellm_reachable, vsellm_error = check_vsellm_reachable()
    embeddings_status, embeddings_error = get_embeddings_status(
        embedding_model=settings.default_embedding_model,
        api_key_configured=settings.vsellm_api_key_configured,
        vsellm_reachable=vsellm_reachable,
        vsellm_error=vsellm_error,
    )
    storage_status = get_storage_status(settings.tmp_dir)

    return HealthResponse(
        status="ok",
        version=settings.app_version,
        environment=settings.app_env,
        uptime_seconds=int(max(0.0, time.monotonic() - _START_TIME_MONOTONIC)),
        vsellm=VseLLMHealth(
            api_key_configured=settings.vsellm_api_key_configured,
            base_url=settings.vsellm_base_url,
            reachable=vsellm_reachable,
        ),
        model=HealthModelInfo(selected=runtime_settings.selected_model),
        files=HealthFilesInfo(enabled=True, status="готов"),
        embeddings=HealthEmbeddingsInfo(
            enabled=True,
            model=settings.default_embedding_model,
            status=embeddings_status,
            last_error=embeddings_error,
        ),
        storage=storage_status,
        session=HealthSessionInfo(enabled=True, active_sessions=session_store.active_sessions_count()),
        last_error=vsellm_error,
    )
