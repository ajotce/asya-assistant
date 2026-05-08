"""user export and deleted user audit tables

Revision ID: 20260508_02
Revises: 20260508_01
Create Date: 2026-05-08 23:45:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260508_02"
down_revision: Union[str, None] = "20260508_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_exports",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.Enum("PENDING", "PROCESSING", "READY", "FAILED", name="user_export_status", native_enum=False), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("download_token", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_exports_user_id", "user_exports", ["user_id"], unique=False)
    op.create_index("ix_user_exports_download_token", "user_exports", ["download_token"], unique=False)
    op.create_index("ix_user_exports_user_status", "user_exports", ["user_id", "status"], unique=False)

    op.create_table(
        "deleted_user_audits",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("had_export", sa.Boolean(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deleted_user_audits_user_id", "deleted_user_audits", ["user_id"], unique=False)
    op.create_index(
        "ix_deleted_user_audits_user_deleted",
        "deleted_user_audits",
        ["user_id", "deleted_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_deleted_user_audits_user_deleted", table_name="deleted_user_audits")
    op.drop_index("ix_deleted_user_audits_user_id", table_name="deleted_user_audits")
    op.drop_table("deleted_user_audits")

    op.drop_index("ix_user_exports_user_status", table_name="user_exports")
    op.drop_index("ix_user_exports_download_token", table_name="user_exports")
    op.drop_index("ix_user_exports_user_id", table_name="user_exports")
    op.drop_table("user_exports")
