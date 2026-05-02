from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps_auth import get_current_admin_user, get_db_session
from app.db.models.access_request import AccessRequest
from app.db.models.user import User
from app.models.schemas import (
    AccessRequestApproveResponse,
    AccessRequestResponse,
    AccessRequestSubmitRequest,
    AccessRequestSubmitResponse,
    AuthUserResponse,
)
from app.services.access_request_service import (
    AccessRequestError,
    AccessRequestNotFoundError,
    AccessRequestService,
)

public_router = APIRouter(prefix="/access-requests", tags=["access-requests"])
admin_router = APIRouter(prefix="/admin/access-requests", tags=["admin-access-requests"])


def _to_access_request_response(request: AccessRequest) -> AccessRequestResponse:
    return AccessRequestResponse(
        id=request.id,
        email=request.email,
        display_name=request.display_name,
        reason=request.reason,
        status=request.status.value,
        approved_by=request.approved_by,
        reviewed_at=request.reviewed_at.isoformat() if request.reviewed_at else None,
        created_at=request.created_at.isoformat(),
        updated_at=request.updated_at.isoformat(),
    )


def _to_user_response(user: User) -> AuthUserResponse:
    return AuthUserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role.value,
        status=user.status.value,
    )


@public_router.post("", response_model=AccessRequestSubmitResponse)
def submit_access_request(
    payload: AccessRequestSubmitRequest,
    session=Depends(get_db_session),
) -> AccessRequestSubmitResponse:
    service = AccessRequestService(session)
    request = service.submit_request(email=payload.email, display_name=payload.display_name, reason=payload.reason)
    return AccessRequestSubmitResponse(status="pending", request=_to_access_request_response(request))


@admin_router.get("", response_model=list[AccessRequestResponse])
def list_access_requests(
    admin_user: User = Depends(get_current_admin_user),
    session=Depends(get_db_session),
) -> list[AccessRequestResponse]:
    _ = admin_user
    service = AccessRequestService(session)
    requests = service.list_requests()
    return [_to_access_request_response(item) for item in requests]


@admin_router.post("/{request_id}/approve", response_model=AccessRequestApproveResponse)
def approve_access_request(
    request_id: str,
    admin_user: User = Depends(get_current_admin_user),
    session=Depends(get_db_session),
) -> AccessRequestApproveResponse:
    service = AccessRequestService(session)
    try:
        request, user, setup_link = service.approve_request(request_id=request_id, admin_user=admin_user)
    except AccessRequestNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AccessRequestError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return AccessRequestApproveResponse(
        status="approved",
        request=_to_access_request_response(request),
        user=_to_user_response(user),
        setup_link=setup_link,
    )


@admin_router.post("/{request_id}/reject", response_model=AccessRequestSubmitResponse)
def reject_access_request(
    request_id: str,
    admin_user: User = Depends(get_current_admin_user),
    session=Depends(get_db_session),
) -> AccessRequestSubmitResponse:
    service = AccessRequestService(session)
    try:
        request = service.reject_request(request_id=request_id, admin_user=admin_user)
    except AccessRequestNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AccessRequestError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return AccessRequestSubmitResponse(status="rejected", request=_to_access_request_response(request))
