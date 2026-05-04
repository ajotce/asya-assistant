"""add document templates table for v0.5

Revision ID: 20260504_04
Revises: 20260504_03
Create Date: 2026-05-04 23:35:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260504_04"
down_revision = "20260504_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_templates",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("file_id", sa.String(length=512), nullable=False),
        sa.Column("fields", sa.JSON(), nullable=False),
        sa.Column("output_settings", sa.JSON(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_document_templates_user_id"), "document_templates", ["user_id"], unique=False)
    op.create_index(
        "ix_document_templates_user_created",
        "document_templates",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_document_templates_user_created", table_name="document_templates")
    op.drop_index(op.f("ix_document_templates_user_id"), table_name="document_templates")
    op.drop_table("document_templates")
