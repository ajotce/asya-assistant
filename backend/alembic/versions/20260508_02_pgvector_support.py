"""add pgvector support for PostgreSQL backend

Revision ID: 20260508_02
Revises: 20260502_08
Create Date: 2026-05-08 16:10:00
"""

from __future__ import annotations

from alembic import op


revision = "20260508_02"
down_revision = "20260502_08"
branch_labels = None
depends_on = None

_EMBEDDING_DIM = 1536


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite/dev path keeps existing storage representation.
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        f"""
        ALTER TABLE memory_chunks
        ALTER COLUMN embedding TYPE vector({_EMBEDDING_DIM})
        USING (
            CASE
                WHEN left(trim(embedding), 1) = '[' THEN embedding::vector({_EMBEDDING_DIM})
                ELSE ('[' || embedding || ']')::vector({_EMBEDDING_DIM})
            END
        )
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("ALTER TABLE memory_chunks ALTER COLUMN embedding TYPE text USING embedding::text")
