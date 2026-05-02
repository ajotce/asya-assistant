"""add diary, observer, private encrypted chat tables and columns

Revision ID: 20260502_07
Revises: 20260502_06
Create Date: 2026-05-02 20:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260502_07"
down_revision = "20260502_06"
branch_labels = None
depends_on = None

chat_kind_enum = sa.Enum("regular", "base", "private_encrypted", name="chat_kind", native_enum=False)


def upgrade() -> None:
    op.create_table(
        "diary_settings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("briefing_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("search_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("memories_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("evening_prompt_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_diary_settings_user_id"),
    )
    op.create_index(op.f("ix_diary_settings_user_id"), "diary_settings", ["user_id"], unique=False)

    op.create_table(
        "diary_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("transcript", sa.Text(), nullable=False),
        sa.Column("topics", sa.JSON(), nullable=False),
        sa.Column("decisions", sa.JSON(), nullable=False),
        sa.Column("mentions", sa.JSON(), nullable=False),
        sa.Column("source_audio_path", sa.String(length=1024), nullable=True),
        sa.Column("processing_status", sa.String(length=32), nullable=False),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_diary_entries_user_id"), "diary_entries", ["user_id"], unique=False)
    op.create_index("ix_diary_entries_user_created", "diary_entries", ["user_id", "created_at"], unique=False)

    op.create_table(
        "observation_rules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("detector", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("threshold_config", sa.JSON(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_observation_rules_user_id"), "observation_rules", ["user_id"], unique=False)
    op.create_index("ix_observation_rules_user_detector", "observation_rules", ["user_id", "detector"], unique=False)

    op.create_table(
        "observations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("rule_id", sa.String(length=36), nullable=True),
        sa.Column("detector", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column(
            "severity",
            sa.Enum("info", "warning", "critical", name="observation_severity", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("new", "seen", "dismissed", "actioned", name="observation_status", native_enum=False),
            nullable=False,
        ),
        sa.Column("context_payload", sa.JSON(), nullable=False),
        sa.Column("dedup_key", sa.String(length=255), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("postponed_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rule_id"], ["observation_rules.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_observations_user_id"), "observations", ["user_id"], unique=False)
    op.create_index("ix_observations_user_status", "observations", ["user_id", "status"], unique=False)
    op.create_index("ix_observations_user_detector", "observations", ["user_id", "detector"], unique=False)
    op.create_index("ix_observations_user_dedup", "observations", ["user_id", "dedup_key"], unique=False)

    op.add_column("messages", sa.Column("content_encrypted", sa.LargeBinary(), nullable=True))
    op.add_column("messages", sa.Column("encryption_salt", sa.String(length=64), nullable=True))

    op.add_column("chats", sa.Column("private_salt", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("chats", "private_salt")
    op.drop_column("messages", "encryption_salt")
    op.drop_column("messages", "content_encrypted")

    op.drop_index("ix_observations_user_dedup", table_name="observations")
    op.drop_index("ix_observations_user_detector", table_name="observations")
    op.drop_index("ix_observations_user_status", table_name="observations")
    op.drop_index(op.f("ix_observations_user_id"), table_name="observations")
    op.drop_table("observations")

    op.drop_index("ix_observation_rules_user_detector", table_name="observation_rules")
    op.drop_index(op.f("ix_observation_rules_user_id"), table_name="observation_rules")
    op.drop_table("observation_rules")

    op.drop_index("ix_diary_entries_user_created", table_name="diary_entries")
    op.drop_index(op.f("ix_diary_entries_user_id"), table_name="diary_entries")
    op.drop_table("diary_entries")

    op.drop_index(op.f("ix_diary_settings_user_id"), table_name="diary_settings")
    op.drop_table("diary_settings")
