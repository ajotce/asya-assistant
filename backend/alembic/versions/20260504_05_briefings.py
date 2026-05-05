"""add briefings and briefing settings

Revision ID: 20260504_05
Revises: 20260504_04
Create Date: 2026-05-04 23:40:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260504_05"
down_revision = "20260504_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "briefing_settings",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("morning_enabled", sa.Boolean(), nullable=False),
        sa.Column("evening_enabled", sa.Boolean(), nullable=False),
        sa.Column("delivery_in_app", sa.Boolean(), nullable=False),
        sa.Column("delivery_telegram", sa.Boolean(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_briefing_settings_user_id", "briefing_settings", ["user_id"], unique=True)

    op.create_table(
        "briefings",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column("delivered_in_app", sa.Boolean(), nullable=False),
        sa.Column("delivered_telegram", sa.Boolean(), nullable=False),
        sa.Column("source_meta", sa.JSON(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_briefings_user_id", "briefings", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_briefings_user_id", table_name="briefings")
    op.drop_table("briefings")
    op.drop_index("ix_briefing_settings_user_id", table_name="briefing_settings")
    op.drop_table("briefing_settings")
