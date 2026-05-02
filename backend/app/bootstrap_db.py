from __future__ import annotations

import sqlite3
import subprocess
from pathlib import Path

from app.core.config import get_settings


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
        (table_name,),
    ).fetchone()
    return row is not None


def _get_alembic_revision(conn: sqlite3.Connection) -> str | None:
    if not _table_exists(conn, "alembic_version"):
        return None
    row = conn.execute("SELECT version_num FROM alembic_version LIMIT 1").fetchone()
    if row is None:
        return None
    revision = row[0]
    return revision if isinstance(revision, str) and revision.strip() else None


def _extract_sqlite_path(db_url: str) -> Path | None:
    prefix = "sqlite+pysqlite:///"
    if not db_url.startswith(prefix):
        return None
    return Path(db_url.removeprefix(prefix))


def _run_alembic(*args: str) -> None:
    subprocess.run(["alembic", *args], check=True)


def main() -> None:
    settings = get_settings()
    db_path = _extract_sqlite_path(settings.asya_db_url)
    if db_path is not None and db_path.exists():
        with sqlite3.connect(db_path) as conn:
            has_users = _table_exists(conn, "users")
            has_spaces = _table_exists(conn, "spaces")
            revision = _get_alembic_revision(conn)
        if has_users and not has_spaces and revision != "20260502_03":
            # Legacy 0.2 DB may contain multi-user tables but miss alembic metadata or have partial revision.
            # Stamp to the last 0.2 revision and then apply v0.3 migration.
            _run_alembic("stamp", "20260502_03")

    _run_alembic("upgrade", "head")


if __name__ == "__main__":
    main()
