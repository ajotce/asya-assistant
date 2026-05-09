"""add briefings and briefing_settings

Revision ID: 20260509_02
Revises: 20260509_01
Create Date: 2026-05-09 12:40:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260509_02"
down_revision = "20260509_01"
branch_labels = None
depends_on = None


briefing_kind_enum = sa.Enum("morning", "evening", name="briefing_kind", native_enum=False)


def upgrade() -> None:
    op.create_table(
        "briefing_settings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Europe/Moscow"),
        sa.Column("morning_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("evening_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("morning_time", sa.String(length=5), nullable=False, server_default="08:00"),
        sa.Column("evening_time", sa.String(length=5), nullable=False, server_default="19:00"),
        sa.Column("channel_in_app", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("channel_telegram", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_briefing_settings_user_id"),
    )
    op.create_index(op.f("ix_briefing_settings_user_id"), "briefing_settings", ["user_id"], unique=False)

    op.create_table(
        "briefings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("kind", briefing_kind_enum, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("delivered_via", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_briefings_user_id"), "briefings", ["user_id"], unique=False)
    op.create_index("ix_briefings_user_kind_created", "briefings", ["user_id", "kind", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_briefings_user_kind_created", table_name="briefings")
    op.drop_index(op.f("ix_briefings_user_id"), table_name="briefings")
    op.drop_table("briefings")
    op.drop_index(op.f("ix_briefing_settings_user_id"), table_name="briefing_settings")
    op.drop_table("briefing_settings")
