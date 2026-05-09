"""add document templates table

Revision ID: 20260509_02
Revises: 20260509_01
Create Date: 2026-05-09 13:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260509_02"
down_revision: Union[str, None] = "20260509_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_templates",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column(
            "provider",
            sa.Enum(
                "google_drive",
                "yandex_disk",
                "onedrive",
                name="document_template_provider",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("file_id", sa.String(length=512), nullable=False),
        sa.Column("fields", sa.JSON(), nullable=False),
        sa.Column("output_settings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_document_templates_created_at"), "document_templates", ["created_at"], unique=False)
    op.create_index(op.f("ix_document_templates_user_id"), "document_templates", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_document_templates_user_id"), table_name="document_templates")
    op.drop_index(op.f("ix_document_templates_created_at"), table_name="document_templates")
    op.drop_table("document_templates")
