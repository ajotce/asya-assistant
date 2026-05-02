from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.core.config import get_settings


def test_alembic_upgrade_head_on_clean_database(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "alembic-upgrade.sqlite3"
    db_url = f"sqlite+pysqlite:///{db_path}"
    monkeypatch.setenv("ASYA_DB_PATH", db_path.as_posix())
    get_settings.cache_clear()

    backend_dir = Path(__file__).resolve().parents[1]
    alembic_ini = backend_dir / "alembic.ini"

    config = Config(alembic_ini.as_posix())
    config.set_main_option("script_location", (backend_dir / "alembic").as_posix())
    config.set_main_option("sqlalchemy.url", db_url)

    command.upgrade(config, "head")

    engine = create_engine(db_url, future=True)
    inspector = inspect(engine)
    assert "users" in inspector.get_table_names()
    assert "usage_records" in inspector.get_table_names()

    with engine.connect() as conn:
        revision = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    assert revision == "20260502_03"
    get_settings.cache_clear()
