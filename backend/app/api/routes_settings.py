from fastapi import APIRouter, Depends, HTTPException

from app.api.deps_auth import get_current_user, get_db_session
from app.core.config import get_settings
from app.db.models.user import User
from app.models.schemas import SettingsResponse, SettingsUpdateRequest
from app.services.settings_service import SettingsService, SettingsValidationError
from sqlalchemy.orm import Session

router = APIRouter(tags=["settings"])


@router.get("/settings", response_model=SettingsResponse)
def get_asya_settings(
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> SettingsResponse:
    service = SettingsService(get_settings(), db_session=db_session)
    return service.get_settings(user_id=current_user.id)


@router.put("/settings", response_model=SettingsResponse)
def update_asya_settings(
    request: SettingsUpdateRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> SettingsResponse:
    service = SettingsService(get_settings(), db_session=db_session)
    try:
        return service.update_settings(request, user_id=current_user.id)
    except SettingsValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
