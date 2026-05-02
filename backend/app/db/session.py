from pathlib import Path
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def _ensure_parent_dir(db_url: str) -> None:
    prefix = "sqlite+pysqlite:///"
    if db_url.startswith(prefix):
        db_path = Path(db_url[len(prefix) :])
        db_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_engine(db_url: str):
    _ensure_parent_dir(db_url)
    return create_engine(db_url, echo=False, future=True)


def get_sessionmaker():
    settings = get_settings()
    engine = get_engine(settings.asya_db_url)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


def create_session() -> Session:
    return get_sessionmaker()()
