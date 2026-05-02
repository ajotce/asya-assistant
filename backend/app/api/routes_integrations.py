from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps_auth import get_current_user, get_db_session
from app.db.models.common import IntegrationProvider
from app.db.models.user import User
from app.models.schemas import IntegrationConnectionResponse
from app.services.integration_connection_service import IntegrationConnectionService

router = APIRouter(tags=["integrations"])


def _parse_provider(raw: str) -> IntegrationProvider:
    try:
        return IntegrationProvider(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Неподдерживаемый provider интеграции.") from exc


def _to_response(item) -> IntegrationConnectionResponse:
    return IntegrationConnectionResponse(
        provider=item.provider.value,
        status=item.status.value,
        scopes=item.scopes or [],
        connected_at=item.connected_at.isoformat() if item.connected_at else None,
        last_refresh_at=item.last_refresh_at.isoformat() if item.last_refresh_at else None,
        last_sync_at=item.last_sync_at.isoformat() if item.last_sync_at else None,
        safe_error_metadata=item.safe_error_metadata,
        created_at=item.created_at.isoformat() if item.created_at else None,
        updated_at=item.updated_at.isoformat() if item.updated_at else None,
    )


@router.get("/integrations", response_model=list[IntegrationConnectionResponse])
def list_integrations(
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> list[IntegrationConnectionResponse]:
    service = IntegrationConnectionService(db_session)
    connections = {item.provider: item for item in service.list_connections(user=current_user)}
    result = []
    for provider in IntegrationProvider:
        item = connections.get(provider) or service.get_connection_or_default(user=current_user, provider=provider)
        result.append(_to_response(item))
    return result


@router.get("/integrations/{provider}", response_model=IntegrationConnectionResponse)
def get_integration(
    provider: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> IntegrationConnectionResponse:
    parsed_provider = _parse_provider(provider)
    service = IntegrationConnectionService(db_session)
    item = service.get_connection_or_default(user=current_user, provider=parsed_provider)
    return _to_response(item)


@router.delete("/integrations/{provider}", response_model=IntegrationConnectionResponse)
def disconnect_integration(
    provider: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> IntegrationConnectionResponse:
    parsed_provider = _parse_provider(provider)
    service = IntegrationConnectionService(db_session)
    item = service.disconnect(user=current_user, provider=parsed_provider)
    return _to_response(item)
