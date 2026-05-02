from sqlalchemy import create_engine, inspect

from app.db.base import Base
from app.db import models  # noqa: F401


def test_sqlalchemy_models_create_expected_tables(tmp_path) -> None:
    db_path = tmp_path / "models-schema.sqlite3"
    engine = create_engine(f"sqlite+pysqlite:///{db_path}", future=True)

    Base.metadata.create_all(engine)
    inspector = inspect(engine)

    table_names = set(inspector.get_table_names())
    assert table_names >= {
        "users",
        "auth_sessions",
        "chats",
        "messages",
        "file_meta",
        "usage_records",
        "access_requests",
        "encrypted_secrets",
        "spaces",
        "space_memory_settings",
        "user_profile_facts",
        "memory_episodes",
        "memory_chunks",
        "behavior_rules",
        "assistant_personality_profiles",
        "memory_changes",
        "memory_snapshots",
        "activity_logs",
    }

    user_indexes = inspector.get_indexes("users")
    user_unique_indexes = {tuple(sorted(item["column_names"])) for item in user_indexes if item.get("unique")}
    assert ("email",) in user_unique_indexes

    encrypted_secret_uniques = {
        tuple(sorted(item["column_names"])) for item in inspector.get_unique_constraints("encrypted_secrets")
    }
    assert ("name", "user_id") in encrypted_secret_uniques

    spaces_uniques = {
        tuple(sorted(item["column_names"])) for item in inspector.get_unique_constraints("spaces")
    }
    assert ("name", "user_id") in spaces_uniques
