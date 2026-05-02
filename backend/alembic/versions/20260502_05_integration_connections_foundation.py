"""add integration connections foundation table

Revision ID: 20260502_05
Revises: 20260502_04
Create Date: 2026-05-02 18:25:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260502_05"
down_revision = "20260502_04"
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
integration_connection_status_enum = sa.Enum(
    "not_connected",
    "connected",
    "expired",
    "revoked",
    "error",
    name="integration_connection_status",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "integration_connections",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("provider", integration_provider_enum, nullable=False),
        sa.Column("status", integration_connection_status_enum, nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_refresh_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("safe_error_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "provider", name="uq_integration_connections_user_provider"),
    )
    op.create_index(op.f("ix_integration_connections_user_id"), "integration_connections", ["user_id"], unique=False)
    op.create_index(
        "ix_integration_connections_user_status",
        "integration_connections",
        ["user_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_integration_connections_user_status", table_name="integration_connections")
    op.drop_index(op.f("ix_integration_connections_user_id"), table_name="integration_connections")
    op.drop_table("integration_connections")
