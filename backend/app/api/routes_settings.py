from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.models.schemas import SettingsResponse, SettingsUpdateRequest
from app.services.settings_service import SettingsService, SettingsValidationError

router = APIRouter(tags=["settings"])


def get_settings_service() -> SettingsService:
    return SettingsService(get_settings())


@router.get("/settings", response_model=SettingsResponse)
def get_asya_settings() -> SettingsResponse:
    service = get_settings_service()
    return service.get_settings()


@router.put("/settings", response_model=SettingsResponse)
def update_asya_settings(request: SettingsUpdateRequest) -> SettingsResponse:
    service = get_settings_service()
    try:
        return service.update_settings(request)
    except SettingsValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
