"""add observer entity snapshots and state changes

Revision ID: 20260504_01
Revises: 20260503_02
Create Date: 2026-05-04 12:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260504_01"
down_revision = "20260503_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "observed_entity_snapshots",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_ref", sa.String(length=255), nullable=False),
        sa.Column("normalized_state", sa.JSON(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "provider",
            "entity_type",
            "entity_ref",
            "digest",
            name="uq_observed_entity_snapshots_dedup",
        ),
    )
    op.create_index(
        "ix_observed_entity_snapshots_user_observed_at",
        "observed_entity_snapshots",
        ["user_id", "observed_at"],
        unique=False,
    )
    op.create_index(
        "ix_observed_entity_snapshots_lookup",
        "observed_entity_snapshots",
        ["user_id", "provider", "entity_type", "entity_ref", "observed_at"],
        unique=False,
    )
    op.create_index("ix_observed_entity_snapshots_user_id", "observed_entity_snapshots", ["user_id"], unique=False)

    op.create_table(
        "observed_entity_state_changes",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("snapshot_id", sa.String(length=36), nullable=False),
        sa.Column("previous_snapshot_id", sa.String(length=36), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_ref", sa.String(length=255), nullable=False),
        sa.Column("change_kind", sa.String(length=64), nullable=False),
        sa.Column("changed_fields", sa.JSON(), nullable=False),
        sa.Column("old_state", sa.JSON(), nullable=False),
        sa.Column("new_state", sa.JSON(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["previous_snapshot_id"], ["observed_entity_snapshots.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["observed_entity_snapshots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_observed_entity_state_changes_user_created",
        "observed_entity_state_changes",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_observed_entity_state_changes_snapshot",
        "observed_entity_state_changes",
        ["snapshot_id"],
        unique=False,
    )
    op.create_index("ix_observed_entity_state_changes_user_id", "observed_entity_state_changes", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_observed_entity_state_changes_user_id", table_name="observed_entity_state_changes")
    op.drop_index("ix_observed_entity_state_changes_snapshot", table_name="observed_entity_state_changes")
    op.drop_index("ix_observed_entity_state_changes_user_created", table_name="observed_entity_state_changes")
    op.drop_table("observed_entity_state_changes")

    op.drop_index("ix_observed_entity_snapshots_user_id", table_name="observed_entity_snapshots")
    op.drop_index("ix_observed_entity_snapshots_lookup", table_name="observed_entity_snapshots")
    op.drop_index("ix_observed_entity_snapshots_user_observed_at", table_name="observed_entity_snapshots")
    op.drop_table("observed_entity_snapshots")
