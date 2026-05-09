from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import MetaData, String, Table, create_engine, func, inspect, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.ddl import sort_tables
from sqlalchemy.sql.sqltypes import Enum as SqlEnum


def _ensure_backend_imports() -> None:
    backend_dir = Path(__file__).resolve().parent
    if backend_dir.as_posix() not in sys.path:
        sys.path.insert(0, backend_dir.as_posix())


def _parse_embedding(raw_value: Any) -> list[float]:
    if isinstance(raw_value, list):
        return [float(v) for v in raw_value]
    if raw_value is None:
        return []
    text = str(raw_value).strip()
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [float(v) for v in parsed]
    return [float(piece) for piece in text.split(",") if piece.strip()]


def _normalize_row_for_destination(table: Table, row: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    normalized = dict(row)
    for column in table.columns:
        if column.name not in normalized:
            continue
        value = normalized[column.name]
        if value is None:
            continue

        if isinstance(column.type, SqlEnum) and isinstance(value, str):
            allowed = set(column.type.enums or [])
            if value in allowed:
                continue
            lowered = value.strip().lower()
            if lowered in allowed:
                normalized[column.name] = lowered
                continue
            return normalized, f"unsupported enum value '{value}' for {table.name}.{column.name}"

        if isinstance(column.type, String) and column.type.length and isinstance(value, str):
            max_len = int(column.type.length)
            if len(value) > max_len:
                normalized[column.name] = value[:max_len]
    return normalized, None


def _migrate_to_postgres(source_url: str, dest_url: str, dry_run: bool) -> int:
    source_engine = create_engine(source_url, future=True)
    dest_engine = create_engine(dest_url, future=True)
    source_inspector = inspect(source_engine)
    target_inspector = inspect(dest_engine)
    source_tables = sorted(t for t in source_inspector.get_table_names() if t != "alembic_version")
    dest_tables = set(target_inspector.get_table_names())

    missing = [name for name in source_tables if name not in dest_tables]
    if missing:
        print(f"Destination DB is missing tables: {', '.join(missing)}", file=sys.stderr)
        return 2

    metadata = MetaData()
    migrated = 0
    total = 0
    skipped_rows = 0

    with source_engine.connect() as source_conn, dest_engine.begin() as dest_conn:
        source_table_map: dict[str, Table] = {
            name: Table(name, metadata, autoload_with=source_conn) for name in source_tables
        }
        migration_order = [table.name for table in sort_tables(source_table_map.values()) if table.name in source_table_map]

        for table_name in migration_order:
            source_table = source_table_map[table_name]
            dest_table = Table(table_name, metadata, autoload_with=dest_conn)
            rows = [dict(row._mapping) for row in source_conn.execute(select(source_table))]
            total += len(rows)
            if not rows:
                continue

            if table_name == "memory_chunks":
                for row in rows:
                    if "embedding" in row:
                        row["embedding"] = _parse_embedding(row["embedding"])

            cleaned_rows: list[dict[str, Any]] = []
            for row in rows:
                normalized, skip_reason = _normalize_row_for_destination(dest_table, row)
                if skip_reason is not None:
                    skipped_rows += 1
                    print(f"[skip] {table_name}: {skip_reason}")
                    continue
                cleaned_rows.append(normalized)

            if dry_run:
                print(f"[dry-run] {table_name}: would process {len(cleaned_rows)} rows")
                continue

            if not cleaned_rows:
                print(f"{table_name}: inserted=0 source={len(rows)}")
                continue

            before_count = int(dest_conn.execute(select(func.count()).select_from(dest_table)).scalar_one())
            pk_columns = [column.name for column in dest_table.primary_key.columns]
            stmt = pg_insert(dest_table).values(cleaned_rows)
            if pk_columns:
                stmt = stmt.on_conflict_do_nothing(index_elements=pk_columns)
            try:
                dest_conn.execute(stmt)
                after_count = int(dest_conn.execute(select(func.count()).select_from(dest_table)).scalar_one())
                inserted = max(0, after_count - before_count)
            except IntegrityError:
                inserted = 0
                for row in cleaned_rows:
                    single_stmt = pg_insert(dest_table).values([row])
                    if pk_columns:
                        single_stmt = single_stmt.on_conflict_do_nothing(index_elements=pk_columns)
                    try:
                        single_before = int(dest_conn.execute(select(func.count()).select_from(dest_table)).scalar_one())
                        dest_conn.execute(single_stmt)
                        single_after = int(dest_conn.execute(select(func.count()).select_from(dest_table)).scalar_one())
                        inserted += max(0, single_after - single_before)
                    except IntegrityError as exc:
                        skipped_rows += 1
                        print(f"[skip] {table_name}: integrity conflict for row ({exc.__class__.__name__})")
            migrated += inserted
            print(f"{table_name}: inserted={inserted} source={len(rows)}")

        print("\nIntegrity check (row counts):")
        for table_name in source_tables:
            source_table = Table(table_name, metadata, autoload_with=source_conn)
            dest_table = Table(table_name, metadata, autoload_with=dest_conn)
            source_count = source_conn.execute(select(func.count()).select_from(source_table)).scalar_one()
            dest_count = dest_conn.execute(select(func.count()).select_from(dest_table)).scalar_one()
            status = "OK" if int(dest_count) >= int(source_count) else "MISMATCH"
            print(f"- {table_name}: source={source_count}, dest={dest_count} [{status}]")

    if dry_run:
        print(f"\n[dry-run] total rows inspected: {total}")
    else:
        print(f"\nInserted rows this run: {migrated} (idempotent run-safe)")
    if skipped_rows:
        print(f"Skipped rows: {skipped_rows}")
    return 0


def main() -> int:
    _ensure_backend_imports()
    parser = argparse.ArgumentParser(prog="python -m backend.cli")
    sub = parser.add_subparsers(dest="entity")

    db_parser = sub.add_parser("db")
    db_sub = db_parser.add_subparsers(dest="db_command")
    migrate_parser = db_sub.add_parser("migrate-to-postgres")
    migrate_parser.add_argument("--source", required=True, help="Source SQLite URL")
    migrate_parser.add_argument("--dest", required=True, help="Destination PostgreSQL URL")
    migrate_parser.add_argument("--dry-run", action="store_true", help="Do not write data")

    args = parser.parse_args()
    if args.entity == "db" and args.db_command == "migrate-to-postgres":
        os.environ.setdefault("ASYA_DATABASE_URL", args.dest)
        return _migrate_to_postgres(source_url=args.source, dest_url=args.dest, dry_run=bool(args.dry_run))

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
