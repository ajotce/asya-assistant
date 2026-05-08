from app.core.config import get_settings


def test_db_backend_detects_sqlite(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "asya.sqlite3"
    monkeypatch.setenv("ASYA_DATABASE_URL", f"sqlite+pysqlite:///{db_path}")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.db_backend == "sqlite"
    get_settings.cache_clear()


def test_db_backend_detects_postgresql(monkeypatch) -> None:
    monkeypatch.setenv(
        "ASYA_DATABASE_URL",
        "postgresql+psycopg://asya:secret@localhost:5432/asya?sslmode=disable",
    )
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.db_backend == "postgresql"
    get_settings.cache_clear()
