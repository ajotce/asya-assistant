"""add user_settings and access_request reason

Revision ID: 20260502_03
Revises: 20260502_02
Create Date: 2026-05-02 11:40:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260502_03"
down_revision = "20260502_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_settings",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("assistant_name", sa.String(length=120), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("selected_model", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.add_column("access_requests", sa.Column("reason", sa.String(length=1000), nullable=True))
    op.execute("UPDATE access_requests SET reason = 'Не указано' WHERE reason IS NULL")
    with op.batch_alter_table("access_requests") as batch_op:
        batch_op.alter_column(
            "reason",
            existing_type=sa.String(length=1000),
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("access_requests") as batch_op:
        batch_op.drop_column("reason")
    op.drop_table("user_settings")
