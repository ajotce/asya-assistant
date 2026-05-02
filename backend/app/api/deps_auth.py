from __future__ import annotations

from typing import Generator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import create_session
from app.db.models.common import UserRole
from app.db.models.user import User
from app.services.auth_service import AuthService


def get_db_session() -> Generator[Session, None, None]:
    session = create_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_auth_service(session: Session = Depends(get_db_session)) -> AuthService:
    return AuthService(session)


def get_current_user(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    settings = get_settings()
    token = request.cookies.get(settings.auth_cookie_name)
    user = auth_service.get_current_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется авторизация.")
    return user


def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Требуются права администратора.")
    return current_user
