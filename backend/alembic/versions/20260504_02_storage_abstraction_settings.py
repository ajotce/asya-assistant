"""add user default storage settings

Revision ID: 20260504_03
Revises: 20260504_02
Create Date: 2026-05-04 22:40:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260504_03"
down_revision = "20260504_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("user_settings") as batch_op:
        batch_op.add_column(sa.Column("default_storage_provider", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("default_storage_folders", sa.JSON(), nullable=True))
    op.execute("UPDATE user_settings SET default_storage_provider = 'google_drive' WHERE default_storage_provider IS NULL")
    op.execute("UPDATE user_settings SET default_storage_folders = '{}' WHERE default_storage_folders IS NULL")
    with op.batch_alter_table("user_settings") as batch_op:
        batch_op.alter_column("default_storage_provider", nullable=False)
        batch_op.alter_column("default_storage_folders", nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("user_settings") as batch_op:
        batch_op.drop_column("default_storage_folders")
        batch_op.drop_column("default_storage_provider")
