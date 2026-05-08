from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKUP_SCRIPT = REPO_ROOT / "infra" / "backup" / "backup_sqlite.sh"


def _create_sqlite_db(db_path: Path) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("CREATE TABLE notes (id INTEGER PRIMARY KEY, text TEXT NOT NULL)")
        connection.execute("INSERT INTO notes(text) VALUES ('hello backup')")
        connection.commit()
    finally:
        connection.close()


def test_backup_script_creates_valid_backup(tmp_path: Path) -> None:
    if shutil.which("sqlite3") is None:
        pytest.skip("sqlite3 command is required for this test")

    source_db = tmp_path / "source.sqlite3"
    backup_dir = tmp_path / "backups"
    _create_sqlite_db(source_db)

    result = subprocess.run(
        [str(BACKUP_SCRIPT), str(source_db), str(backup_dir)],
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stderr

    backups = sorted(backup_dir.glob("asya_backup_*.db"))
    assert len(backups) == 1

    integrity = subprocess.run(
        ["sqlite3", str(backups[0]), "PRAGMA integrity_check;"],
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert integrity.returncode == 0
    assert integrity.stdout.strip().lower() == "ok"


def test_backup_retention_keeps_latest_30(tmp_path: Path) -> None:
    if shutil.which("sqlite3") is None:
        pytest.skip("sqlite3 command is required for this test")

    source_db = tmp_path / "source.sqlite3"
    backup_dir = tmp_path / "backups"
    _create_sqlite_db(source_db)
    backup_dir.mkdir(parents=True, exist_ok=True)

    for index in range(1, 32):
        file_name = f"asya_backup_202401{index:02d}_010101.db"
        dummy_backup = backup_dir / file_name
        dummy_backup.write_bytes(b"legacy-backup")

    oldest = backup_dir / "asya_backup_20240101_010101.db"
    assert oldest.exists()

    env = os.environ.copy()
    env["TZ"] = "UTC"
    result = subprocess.run(
        [str(BACKUP_SCRIPT), str(source_db), str(backup_dir)],
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
    )
    assert result.returncode == 0, result.stderr

    backups = sorted(backup_dir.glob("asya_backup_*.db"))
    assert len(backups) == 30
    assert not oldest.exists()
