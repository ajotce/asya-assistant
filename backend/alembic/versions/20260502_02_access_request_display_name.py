"""add display_name to access_requests

Revision ID: 20260502_02
Revises: 20260502_01
Create Date: 2026-05-02 03:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260502_02"
down_revision = "20260502_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("access_requests", sa.Column("display_name", sa.String(length=120), nullable=True))
    op.execute("UPDATE access_requests SET display_name = 'Unknown' WHERE display_name IS NULL")
    with op.batch_alter_table("access_requests") as batch_op:
        batch_op.alter_column(
            "display_name",
            existing_type=sa.String(length=120),
            nullable=False,
        )


def downgrade() -> None:
    op.drop_column("access_requests", "display_name")
