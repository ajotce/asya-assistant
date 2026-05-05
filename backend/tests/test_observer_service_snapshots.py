from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.models.common import IntegrationConnectionStatus, IntegrationProvider, UserStatus
from app.repositories.integration_connection_repository import IntegrationConnectionRepository
from app.repositories.observation_repository import ObservationRepository
from app.repositories.user_repository import UserRepository
from app.services.observer_service import ObserverService
from tests.auth_helpers import setup_test_db


def _create_user(session: Session, *, email: str):
    user = UserRepository(session).create(
        email=email,
        display_name="Observer",
        password_hash="hash",
        status=UserStatus.ACTIVE,
    )
    session.commit()
    return user


def test_observer_creates_history_based_observations_from_snapshots(monkeypatch, tmp_path) -> None:
    _, engine = setup_test_db(tmp_path, monkeypatch)

    with Session(bind=engine) as session:
        user = _create_user(session, email="history@example.com")
        repo = IntegrationConnectionRepository(session)

        old = (datetime.now(timezone.utc) - timedelta(days=9)).isoformat()
        due_1 = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        due_2 = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
        due_3 = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()

        repo.upsert(
            user_id=user.id,
            provider=IntegrationProvider.TODOIST,
            status=IntegrationConnectionStatus.CONNECTED,
            scopes=["tasks:read"],
            safe_error_metadata={
                "tasks": [
                    {
                        "id": "task-1",
                        "status": "open",
                        "due_at": due_1,
                        "updated_at": old,
                    }
                ]
            },
        )
        session.commit()

        service = ObserverService(session)
        service.run_for_user(user)

        repo.upsert(
            user_id=user.id,
            provider=IntegrationProvider.TODOIST,
            status=IntegrationConnectionStatus.CONNECTED,
            scopes=["tasks:read"],
            safe_error_metadata={
                "tasks": [
                    {
                        "id": "task-1",
                        "status": "open",
                        "due_at": due_2,
                        "updated_at": old,
                    }
                ]
            },
        )
        session.commit()
        service.run_for_user(user)

        repo.upsert(
            user_id=user.id,
            provider=IntegrationProvider.TODOIST,
            status=IntegrationConnectionStatus.CONNECTED,
            scopes=["tasks:read"],
            safe_error_metadata={
                "tasks": [
                    {
                        "id": "task-1",
                        "status": "open",
                        "due_at": due_3,
                        "updated_at": old,
                    }
                ]
            },
        )
        session.commit()
        service.run_for_user(user)

        observations = ObservationRepository(session).list_for_user(user.id, limit=100)
        detectors = {item.detector for item in observations}

        assert "RepeatedRescheduling" in detectors
        assert "StaleTask" in detectors
        assert "DeadlineDrift" in detectors
