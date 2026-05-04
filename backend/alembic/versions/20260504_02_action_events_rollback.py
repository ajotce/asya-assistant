"""add action_events with rollback metadata for v0.5

Revision ID: 20260504_02
Revises: 20260504_01
Create Date: 2026-05-04 18:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260504_02"
down_revision = "20260504_01"
branch_labels = None
depends_on = None


rollback_status_enum = sa.Enum(
    "not_requested",
    "previewed",
    "executed",
    "skipped",
    "failed",
    name="rollback_status",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "action_events",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("activity_log_id", sa.String(length=36), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("operation", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=255), nullable=True),
        sa.Column("reversible", sa.Boolean(), nullable=False),
        sa.Column("rollback_status", rollback_status_enum, nullable=False),
        sa.Column("rollback_strategy", sa.String(length=64), nullable=True),
        sa.Column("rollback_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("previous_state", sa.JSON(), nullable=True),
        sa.Column("safe_metadata", sa.JSON(), nullable=True),
        sa.Column("rollback_notes", sa.Text(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["activity_log_id"], ["activity_logs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_action_events_user_id"), "action_events", ["user_id"], unique=False)
    op.create_index("ix_action_events_user_created", "action_events", ["user_id", "created_at"], unique=False)
    op.create_index("ix_action_events_user_reversible", "action_events", ["user_id", "reversible"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_action_events_user_reversible", table_name="action_events")
    op.drop_index("ix_action_events_user_created", table_name="action_events")
    op.drop_index(op.f("ix_action_events_user_id"), table_name="action_events")
    op.drop_table("action_events")
