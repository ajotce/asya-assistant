"""add oauth states table for pkce flow

Revision ID: 20260502_06
Revises: 20260502_05
Create Date: 2026-05-02 19:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260502_06"
down_revision = "20260502_05"
branch_labels = None
depends_on = None


integration_provider_enum = sa.Enum(
    "linear",
    "google_calendar",
    "todoist",
    "gmail",
    "google_drive",
    "telegram",
    name="integration_provider",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "oauth_states",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("provider", integration_provider_enum, nullable=False),
        sa.Column("state_token", sa.String(length=255), nullable=False),
        sa.Column("code_verifier", sa.String(length=255), nullable=False),
        sa.Column("redirect_uri", sa.String(length=1000), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("safe_error_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("state_token", name="uq_oauth_states_state_token"),
    )
    op.create_index(op.f("ix_oauth_states_user_id"), "oauth_states", ["user_id"], unique=False)
    op.create_index("ix_oauth_states_user_provider", "oauth_states", ["user_id", "provider"], unique=False)
    op.create_index("ix_oauth_states_expires_at", "oauth_states", ["expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_oauth_states_expires_at", table_name="oauth_states")
    op.drop_index("ix_oauth_states_user_provider", table_name="oauth_states")
    op.drop_index(op.f("ix_oauth_states_user_id"), table_name="oauth_states")
    op.drop_table("oauth_states")
