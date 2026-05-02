from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models.common import ActivityEntityType, ActivityEventType, MemoryStatus
from app.repositories.activity_log_repository import ActivityLogRepository
from app.repositories.space_repository import SpaceRepository
from app.repositories.user_profile_fact_repository import UserProfileFactRepository
from app.repositories.user_repository import UserRepository


def test_space_and_memory_repositories_are_user_scoped(tmp_path) -> None:
    db_path = tmp_path / "memory-repositories.sqlite3"
    engine = create_engine(f"sqlite+pysqlite:///{db_path}", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user_repo = UserRepository(session)
        user_a = user_repo.create(email="a@example.com", display_name="A", password_hash="x")
        user_b = user_repo.create(email="b@example.com", display_name="B", password_hash="x")
        user_a_id = user_a.id
        user_b_id = user_b.id

        space_repo = SpaceRepository(session)
        space_a = space_repo.create(user_id=user_a_id, name="Work")
        space_repo.create(user_id=user_b_id, name="Personal")

        fact_repo = UserProfileFactRepository(session)
        fact_a = fact_repo.create(
            user_id=user_a_id,
            space_id=space_a.id,
            key="preferred_language",
            value="ru",
            status=MemoryStatus.CONFIRMED,
        )
        fact_repo.create(
            user_id=user_b_id,
            key="timezone",
            value="UTC",
            status=MemoryStatus.NEEDS_REVIEW,
        )

        log_repo = ActivityLogRepository(session)
        log_repo.create(
            user_id=user_a_id,
            space_id=space_a.id,
            event_type=ActivityEventType.MEMORY_FACT_CREATED,
            entity_type=ActivityEntityType.USER_PROFILE_FACT,
            entity_id=fact_a.id,
            summary="Fact stored",
        )

        session.commit()

    with Session(engine) as session:
        space_repo = SpaceRepository(session)
        fact_repo = UserProfileFactRepository(session)
        log_repo = ActivityLogRepository(session)

        spaces_for_a = space_repo.list_for_user(user_a_id)
        spaces_for_b = space_repo.list_for_user(user_b_id)
        assert len(spaces_for_a) == 1
        assert len(spaces_for_b) == 1
        assert spaces_for_a[0].user_id == user_a_id
        assert spaces_for_b[0].user_id == user_b_id

        facts_for_a = fact_repo.list_for_user(user_a_id)
        facts_for_b = fact_repo.list_for_user(user_b_id)
        assert len(facts_for_a) == 1
        assert len(facts_for_b) == 1
        assert fact_repo.get_for_user(facts_for_a[0].id, user_b_id) is None

        logs_for_a = log_repo.list_for_user(user_a_id)
        logs_for_b = log_repo.list_for_user(user_b_id)
        assert len(logs_for_a) == 1
        assert logs_for_b == []
