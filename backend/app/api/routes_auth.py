from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from app.api.deps_auth import get_auth_service, get_current_user, get_db_session
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.db.models.user import User
from app.models.schemas import (
    AuthLoginRequest,
    AuthRegisterRequest,
    AuthRegisterResponse,
    AuthSetupPasswordRequest,
    AuthUserResponse,
)
from app.services.access_request_service import AccessRequestService, SignupTokenError
from app.services.auth_service import AuthError, AuthService, RegistrationClosedError, RegistrationModeError

router = APIRouter(prefix="/auth", tags=["auth"])


def _to_user_response(user: User, preferred_chat_id: str | None = None) -> AuthUserResponse:
    return AuthUserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role.value,
        status=user.status.value,
        preferred_chat_id=preferred_chat_id,
        onboarding_completed=user.onboarding_completed,
    )


def _register_impl(
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
    except RegistrationModeError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/register", response_model=AuthRegisterResponse)
def register(
    payload: AuthRegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthRegisterResponse:
    return _register_impl(payload=payload, auth_service=auth_service)


@router.post("/signup", response_model=AuthRegisterResponse)
@limiter.limit("10/minute")
def signup(
    request: Request,
    payload: AuthRegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthRegisterResponse:
    _ = request
    return _register_impl(payload=payload, auth_service=auth_service)


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


@router.post("/setup-password", response_model=AuthUserResponse)
def setup_password(
    payload: AuthSetupPasswordRequest,
    response: Response,
    session=Depends(get_db_session),
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthUserResponse:
    access_service = AccessRequestService(session)
    password_hash = auth_service.hash_password(payload.password)
    try:
        user = access_service.complete_signup_with_token(raw_token=payload.token, password_hash=password_hash)
    except SignupTokenError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    user, raw_token, preferred_chat_id = auth_service.login(email=user.email, password=payload.password)
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


@router.post("/onboarding/complete", response_model=AuthUserResponse)
def complete_onboarding(
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthUserResponse:
    user = auth_service.mark_onboarding_completed(current_user)
    preferred_chat_id = auth_service.get_preferred_chat_id(user.id)
    return _to_user_response(user, preferred_chat_id=preferred_chat_id)


@router.get("/oauth/{provider}/callback", response_model=AuthUserResponse)
@limiter.limit("10/minute")
def oauth_callback(
    request: Request,
    provider: str,
    response: Response,
    email: str = Query(min_length=3, max_length=320),
    display_name: str = Query(default="", max_length=120),
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthUserResponse:
    _ = request
    normalized_provider = provider.strip().lower()
    if normalized_provider not in {"google", "yandex"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неподдерживаемый OAuth provider.")
    try:
        user, raw_token, preferred_chat_id = auth_service.oauth_login_or_register(
            email=email.strip().lower(),
            display_name=display_name.strip(),
            provider=normalized_provider,
        )
    except (RegistrationClosedError, RegistrationModeError) as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

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
