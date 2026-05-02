"""add signup_tokens for one-time password setup links

Revision ID: 20260502_08
Revises: 20260502_07
Create Date: 2026-05-02 22:40:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260502_08"
down_revision = ("20260502_07", "20260502_07b")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signup_tokens",
        sa.Column("access_request_id", sa.String(length=36), nullable=True),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["access_request_id"], ["access_requests.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_signup_tokens_email"), "signup_tokens", ["email"], unique=False)
    op.create_index("ix_signup_tokens_email_expires", "signup_tokens", ["email", "expires_at"], unique=False)
    op.create_index(op.f("ix_signup_tokens_token_hash"), "signup_tokens", ["token_hash"], unique=True)
    op.create_index(op.f("ix_signup_tokens_user_id"), "signup_tokens", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_signup_tokens_user_id"), table_name="signup_tokens")
    op.drop_index(op.f("ix_signup_tokens_token_hash"), table_name="signup_tokens")
    op.drop_index("ix_signup_tokens_email_expires", table_name="signup_tokens")
    op.drop_index(op.f("ix_signup_tokens_email"), table_name="signup_tokens")
    op.drop_table("signup_tokens")
