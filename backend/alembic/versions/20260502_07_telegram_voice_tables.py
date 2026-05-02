"""add telegram_account_links, telegram_link_tokens, user_voice_settings

Revision ID: 20260502_07
Revises: 20260502_06
Create Date: 2026-05-02 20:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260502_07b"
down_revision = "20260502_06"
branch_labels = None
depends_on = None


voice_gender_enum = sa.Enum("female", "male", "neutral", name="voice_gender", native_enum=False)
voice_provider_stt_enum = sa.Enum("mock", "yandex_speechkit", "gigachat", name="voice_provider_stt", native_enum=False)
voice_provider_tts_enum = sa.Enum("mock", "yandex_speechkit", "gigachat", name="voice_provider_tts", native_enum=False)


def upgrade() -> None:
    op.create_table(
        "telegram_account_links",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("telegram_user_id", sa.String(length=64), nullable=False),
        sa.Column("telegram_chat_id", sa.String(length=64), nullable=False),
        sa.Column("telegram_username", sa.String(length=255), nullable=True),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("unlinked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_user_id", name="uq_telegram_account_links_tg_user"),
    )
    op.create_index(op.f("ix_telegram_account_links_user_id"), "telegram_account_links", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_telegram_account_links_telegram_user_id"),
        "telegram_account_links",
        ["telegram_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_telegram_account_links_user_active",
        "telegram_account_links",
        ["user_id", "is_active"],
        unique=False,
    )

    op.create_table(
        "telegram_link_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_by_telegram_user_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_telegram_link_tokens_hash"),
    )
    op.create_index(op.f("ix_telegram_link_tokens_user_id"), "telegram_link_tokens", ["user_id"], unique=False)
    op.create_index(
        "ix_telegram_link_tokens_user_expires",
        "telegram_link_tokens",
        ["user_id", "expires_at"],
        unique=False,
    )

    op.create_table(
        "user_voice_settings",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("assistant_name", sa.String(length=120), nullable=False),
        sa.Column("voice_gender", voice_gender_enum, nullable=False),
        sa.Column("stt_provider", voice_provider_stt_enum, nullable=False),
        sa.Column("tts_provider", voice_provider_tts_enum, nullable=False),
        sa.Column("tts_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("user_voice_settings")
    op.drop_index("ix_telegram_link_tokens_user_expires", table_name="telegram_link_tokens")
    op.drop_index(op.f("ix_telegram_link_tokens_user_id"), table_name="telegram_link_tokens")
    op.drop_table("telegram_link_tokens")
    op.drop_index("ix_telegram_account_links_user_active", table_name="telegram_account_links")
    op.drop_index(op.f("ix_telegram_account_links_telegram_user_id"), table_name="telegram_account_links")
    op.drop_index(op.f("ix_telegram_account_links_user_id"), table_name="telegram_account_links")
    op.drop_table("telegram_account_links")
