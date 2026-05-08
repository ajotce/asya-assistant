"""add user export and deletion audit tables

Revision ID: 20260508_03
Revises: 20260502_04
Create Date: 2026-05-08 16:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260508_03"
down_revision = "20260502_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_exports",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("object_key", sa.String(length=1024), nullable=True),
        sa.Column("download_url", sa.String(length=2048), nullable=True),
        sa.Column("download_token", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.String(length=2000), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_exports_user_id"), "user_exports", ["user_id"], unique=False)
    op.create_index(op.f("ix_user_exports_download_token"), "user_exports", ["download_token"], unique=False)
    op.create_index("ix_user_exports_user_created", "user_exports", ["user_id", "created_at"], unique=False)
    op.create_index("ix_user_exports_user_status", "user_exports", ["user_id", "status"], unique=False)

    op.create_table(
        "deleted_user_audit",
        sa.Column("deleted_user_id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("initiated_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("export_id", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_deleted_user_audit_deleted_user_id"), "deleted_user_audit", ["deleted_user_id"], unique=False)
    op.create_index(op.f("ix_deleted_user_audit_deleted_at"), "deleted_user_audit", ["deleted_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_deleted_user_audit_deleted_at"), table_name="deleted_user_audit")
    op.drop_index(op.f("ix_deleted_user_audit_deleted_user_id"), table_name="deleted_user_audit")
    op.drop_table("deleted_user_audit")

    op.drop_index("ix_user_exports_user_status", table_name="user_exports")
    op.drop_index("ix_user_exports_user_created", table_name="user_exports")
    op.drop_index(op.f("ix_user_exports_download_token"), table_name="user_exports")
    op.drop_index(op.f("ix_user_exports_user_id"), table_name="user_exports")
    op.drop_table("user_exports")
