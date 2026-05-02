from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.api.deps_auth import get_auth_service, get_current_user
from app.core.config import get_settings
from app.db.models.user import User
from app.models.schemas import (
    AuthLoginRequest,
    AuthRegisterRequest,
    AuthRegisterResponse,
    AuthUserResponse,
)
from app.services.auth_service import AuthError, AuthService, RegistrationClosedError

router = APIRouter(prefix="/auth", tags=["auth"])


def _to_user_response(user: User, preferred_chat_id: str | None = None) -> AuthUserResponse:
    return AuthUserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role.value,
        status=user.status.value,
        preferred_chat_id=preferred_chat_id,
    )


@router.post("/register", response_model=AuthRegisterResponse)
def register(
    payload: AuthRegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthRegisterResponse:
    try:
        user = auth_service.register(
            email=payload.email.strip().lower(),
            display_name=payload.display_name.strip(),
            password=payload.password,
        )
        return AuthRegisterResponse(status="registered", user=_to_user_response(user))
    except RegistrationClosedError as exc:
        return AuthRegisterResponse(status="request_saved", detail=str(exc))
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/login", response_model=AuthUserResponse)
def login(
    payload: AuthLoginRequest,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthUserResponse:
    try:
        user, raw_token, preferred_chat_id = auth_service.login(
            email=payload.email.strip().lower(),
            password=payload.password,
        )
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    settings = get_settings()
    max_age = settings.auth_session_ttl_hours * 3600
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=raw_token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        max_age=max_age,
    )
    return _to_user_response(user, preferred_chat_id=preferred_chat_id)


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict[str, str]:
    settings = get_settings()
    token = request.cookies.get(settings.auth_cookie_name)
    auth_service.logout(token)
    # Пользователь уже авторизован; revoke текущей сессии через cookie.
    response.delete_cookie(key=settings.auth_cookie_name, httponly=True, samesite="lax")
    return {"status": "ok"}


@router.get("/me", response_model=AuthUserResponse)
def me(
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthUserResponse:
    preferred_chat_id = auth_service.get_preferred_chat_id(current_user.id)
    return _to_user_response(current_user, preferred_chat_id=preferred_chat_id)
