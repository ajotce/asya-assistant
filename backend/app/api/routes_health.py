from fastapi import APIRouter

from app.core.config import get_settings
from app.models.schemas import HealthResponse, VseLLMHealth

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        environment=settings.app_env,
        vsellm=VseLLMHealth(
            api_key_configured=settings.vsellm_api_key_configured,
            base_url=settings.vsellm_base_url,
        ),
    )
