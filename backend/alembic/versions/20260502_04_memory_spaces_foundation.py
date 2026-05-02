"""add asya 0.3 memory spaces foundation tables

Revision ID: 20260502_04
Revises: 20260502_03
Create Date: 2026-05-02 14:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260502_04"
down_revision = "20260502_03"
branch_labels = None
depends_on = None


memory_status_enum = sa.Enum(
    "confirmed",
    "inferred",
    "needs_review",
    "outdated",
    "forbidden",
    "deleted",
    name="memory_status",
    native_enum=False,
)
rule_scope_enum = sa.Enum("global", "user", "space", name="rule_scope", native_enum=False)
rule_strictness_enum = sa.Enum("soft", "normal", "hard", name="rule_strictness", native_enum=False)
rule_status_enum = sa.Enum("active", "disabled", "archived", name="rule_status", native_enum=False)
rule_source_enum = sa.Enum("user", "assistant", "system", name="rule_source", native_enum=False)
personality_scope_enum = sa.Enum("base", "space_overlay", name="personality_scope", native_enum=False)
memory_change_kind_enum = sa.Enum(
    "create",
    "update",
    "status",
    "delete",
    "rollback",
    name="memory_change_kind",
    native_enum=False,
)
activity_event_type_enum = sa.Enum(
    "space_created",
    "space_updated",
    "space_archived",
    "memory_fact_created",
    "memory_episode_created",
    "memory_status_changed",
    "rule_applied",
    "personality_applied",
    "memory_snapshot_created",
    "memory_rollback",
    name="activity_event_type",
    native_enum=False,
)
activity_entity_type_enum = sa.Enum(
    "space",
    "space_settings",
    "user_profile_fact",
    "memory_episode",
    "memory_chunk",
    "behavior_rule",
    "personality_profile",
    "memory_change",
    "memory_snapshot",
    name="activity_entity_type",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "spaces",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False),
        sa.Column("is_admin_only", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_spaces_user_name"),
    )
    op.create_index(op.f("ix_spaces_user_id"), "spaces", ["user_id"], unique=False)
    op.create_index("ix_spaces_user_archived", "spaces", ["user_id", "is_archived"], unique=False)

    with op.batch_alter_table("chats") as batch_op:
        batch_op.add_column(sa.Column("space_id", sa.String(length=36), nullable=True))
        batch_op.create_index("ix_chats_space_id", ["space_id"], unique=False)
        batch_op.create_index("ix_chats_user_id_space_id", ["user_id", "space_id"], unique=False)
        batch_op.create_foreign_key("fk_chats_space_id_spaces", "spaces", ["space_id"], ["id"], ondelete="SET NULL")

    op.create_table(
        "space_memory_settings",
        sa.Column("space_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("memory_read_enabled", sa.Boolean(), nullable=False),
        sa.Column("memory_write_enabled", sa.Boolean(), nullable=False),
        sa.Column("behavior_rules_enabled", sa.Boolean(), nullable=False),
        sa.Column("personality_overlay_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("space_id"),
    )
    op.create_index(op.f("ix_space_memory_settings_user_id"), "space_memory_settings", ["user_id"], unique=False)

    op.create_table(
        "user_profile_facts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("space_id", sa.String(length=36), nullable=True),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("status", memory_status_enum, nullable=False),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_profile_facts_user_id"), "user_profile_facts", ["user_id"], unique=False)
    op.create_index("ix_user_profile_facts_user_space", "user_profile_facts", ["user_id", "space_id"], unique=False)
    op.create_index("ix_user_profile_facts_user_status", "user_profile_facts", ["user_id", "status"], unique=False)

    op.create_table(
        "memory_episodes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("chat_id", sa.String(length=36), nullable=False),
        sa.Column("space_id", sa.String(length=36), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("status", memory_status_enum, nullable=False),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_memory_episodes_chat_id"), "memory_episodes", ["chat_id"], unique=False)
    op.create_index(op.f("ix_memory_episodes_user_id"), "memory_episodes", ["user_id"], unique=False)
    op.create_index("ix_memory_episodes_user_space", "memory_episodes", ["user_id", "space_id"], unique=False)
    op.create_index("ix_memory_episodes_user_status", "memory_episodes", ["user_id", "status"], unique=False)

    op.create_table(
        "memory_chunks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("memory_episode_id", sa.String(length=36), nullable=False),
        sa.Column("space_id", sa.String(length=36), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding_model", sa.String(length=255), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["memory_episode_id"], ["memory_episodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_memory_chunks_memory_episode_id"), "memory_chunks", ["memory_episode_id"], unique=False)
    op.create_index(op.f("ix_memory_chunks_user_id"), "memory_chunks", ["user_id"], unique=False)
    op.create_index("ix_memory_chunks_episode_position", "memory_chunks", ["memory_episode_id", "chunk_index"], unique=False)
    op.create_index("ix_memory_chunks_user_space", "memory_chunks", ["user_id", "space_id"], unique=False)

    op.create_table(
        "behavior_rules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("space_id", sa.String(length=36), nullable=True),
        sa.Column("scope", rule_scope_enum, nullable=False),
        sa.Column("strictness", rule_strictness_enum, nullable=False),
        sa.Column("status", rule_status_enum, nullable=False),
        sa.Column("source", rule_source_enum, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("instruction", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_behavior_rules_user_id"), "behavior_rules", ["user_id"], unique=False)
    op.create_index("ix_behavior_rules_user_scope", "behavior_rules", ["user_id", "scope"], unique=False)
    op.create_index("ix_behavior_rules_user_space", "behavior_rules", ["user_id", "space_id"], unique=False)
    op.create_index("ix_behavior_rules_user_status", "behavior_rules", ["user_id", "status"], unique=False)

    op.create_table(
        "assistant_personality_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("space_id", sa.String(length=36), nullable=True),
        sa.Column("scope", personality_scope_enum, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("tone", sa.String(length=120), nullable=False),
        sa.Column("style_notes", sa.Text(), nullable=False),
        sa.Column("humor_level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("initiative_level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("can_gently_disagree", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("address_user_by_name", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "scope", "space_id", name="uq_personality_user_scope_space"),
    )
    op.create_index(op.f("ix_assistant_personality_profiles_user_id"), "assistant_personality_profiles", ["user_id"], unique=False)
    op.create_index("ix_personality_profiles_user_scope", "assistant_personality_profiles", ["user_id", "scope"], unique=False)

    op.create_table(
        "memory_changes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("space_id", sa.String(length=36), nullable=True),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("change_kind", memory_change_kind_enum, nullable=False),
        sa.Column("old_value", sa.JSON(), nullable=True),
        sa.Column("new_value", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_memory_changes_entity_id"), "memory_changes", ["entity_id"], unique=False)
    op.create_index(op.f("ix_memory_changes_user_id"), "memory_changes", ["user_id"], unique=False)
    op.create_index("ix_memory_changes_user_space", "memory_changes", ["user_id", "space_id"], unique=False)

    op.create_table(
        "memory_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("space_id", sa.String(length=36), nullable=True),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_memory_snapshots_user_id"), "memory_snapshots", ["user_id"], unique=False)
    op.create_index("ix_memory_snapshots_user_space", "memory_snapshots", ["user_id", "space_id"], unique=False)

    op.create_table(
        "activity_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("space_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", activity_event_type_enum, nullable=False),
        sa.Column("entity_type", activity_entity_type_enum, nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_activity_logs_user_id"), "activity_logs", ["user_id"], unique=False)
    op.create_index("ix_activity_logs_user_created", "activity_logs", ["user_id", "created_at"], unique=False)
    op.create_index("ix_activity_logs_user_space", "activity_logs", ["user_id", "space_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_activity_logs_user_space", table_name="activity_logs")
    op.drop_index("ix_activity_logs_user_created", table_name="activity_logs")
    op.drop_index(op.f("ix_activity_logs_user_id"), table_name="activity_logs")
    op.drop_table("activity_logs")

    op.drop_index("ix_memory_snapshots_user_space", table_name="memory_snapshots")
    op.drop_index(op.f("ix_memory_snapshots_user_id"), table_name="memory_snapshots")
    op.drop_table("memory_snapshots")

    op.drop_index("ix_memory_changes_user_space", table_name="memory_changes")
    op.drop_index(op.f("ix_memory_changes_user_id"), table_name="memory_changes")
    op.drop_index(op.f("ix_memory_changes_entity_id"), table_name="memory_changes")
    op.drop_table("memory_changes")

    op.drop_index("ix_personality_profiles_user_scope", table_name="assistant_personality_profiles")
    op.drop_index(op.f("ix_assistant_personality_profiles_user_id"), table_name="assistant_personality_profiles")
    op.drop_table("assistant_personality_profiles")

    op.drop_index("ix_behavior_rules_user_status", table_name="behavior_rules")
    op.drop_index("ix_behavior_rules_user_space", table_name="behavior_rules")
    op.drop_index("ix_behavior_rules_user_scope", table_name="behavior_rules")
    op.drop_index(op.f("ix_behavior_rules_user_id"), table_name="behavior_rules")
    op.drop_table("behavior_rules")

    op.drop_index("ix_memory_chunks_user_space", table_name="memory_chunks")
    op.drop_index("ix_memory_chunks_episode_position", table_name="memory_chunks")
    op.drop_index(op.f("ix_memory_chunks_user_id"), table_name="memory_chunks")
    op.drop_index(op.f("ix_memory_chunks_memory_episode_id"), table_name="memory_chunks")
    op.drop_table("memory_chunks")

    op.drop_index("ix_memory_episodes_user_status", table_name="memory_episodes")
    op.drop_index("ix_memory_episodes_user_space", table_name="memory_episodes")
    op.drop_index(op.f("ix_memory_episodes_user_id"), table_name="memory_episodes")
    op.drop_index(op.f("ix_memory_episodes_chat_id"), table_name="memory_episodes")
    op.drop_table("memory_episodes")

    op.drop_index("ix_user_profile_facts_user_status", table_name="user_profile_facts")
    op.drop_index("ix_user_profile_facts_user_space", table_name="user_profile_facts")
    op.drop_index(op.f("ix_user_profile_facts_user_id"), table_name="user_profile_facts")
    op.drop_table("user_profile_facts")

    op.drop_index(op.f("ix_space_memory_settings_user_id"), table_name="space_memory_settings")
    op.drop_table("space_memory_settings")

    with op.batch_alter_table("chats") as batch_op:
        batch_op.drop_constraint("fk_chats_space_id_spaces", type_="foreignkey")
        batch_op.drop_index("ix_chats_user_id_space_id")
        batch_op.drop_index("ix_chats_space_id")
        batch_op.drop_column("space_id")

    op.drop_index("ix_spaces_user_archived", table_name="spaces")
    op.drop_index(op.f("ix_spaces_user_id"), table_name="spaces")
    op.drop_table("spaces")
