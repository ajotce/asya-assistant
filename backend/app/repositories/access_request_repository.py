from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.access_request import AccessRequest
from app.db.models.common import AccessRequestStatus


class AccessRequestRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, request_id: str) -> AccessRequest | None:
        return self._session.get(AccessRequest, request_id)

    def get_pending_by_email(self, email: str) -> AccessRequest | None:
        stmt = select(AccessRequest).where(
            AccessRequest.email == email,
            AccessRequest.status == AccessRequestStatus.PENDING,
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def list_requests(self) -> list[AccessRequest]:
        stmt = select(AccessRequest).order_by(AccessRequest.created_at.desc())
        return list(self._session.execute(stmt).scalars())

    def create(self, *, email: str, display_name: str, reason: str) -> AccessRequest:
        req = AccessRequest(
            email=email,
            display_name=display_name,
            reason=reason,
            status=AccessRequestStatus.PENDING,
            token_hash=None,
            approved_by=None,
            expires_at=None,
            reviewed_at=None,
        )
        self._session.add(req)
        self._session.flush()
        return req

    def save(self, request: AccessRequest) -> AccessRequest:
        self._session.add(request)
        self._session.flush()
        return request
