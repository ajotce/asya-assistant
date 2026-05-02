"""initial multi-user foundation schema

Revision ID: 20260502_01
Revises:
Create Date: 2026-05-02 01:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260502_01"
down_revision = None
branch_labels = None
depends_on = None


user_role_enum = sa.Enum("user", "admin", name="user_role", native_enum=False)
user_status_enum = sa.Enum("pending", "active", "disabled", name="user_status", native_enum=False)
chat_kind_enum = sa.Enum("regular", "base", name="chat_kind", native_enum=False)
message_role_enum = sa.Enum("user", "assistant", "system", "tool", name="message_role", native_enum=False)
access_request_status_enum = sa.Enum(
    "pending",
    "approved",
    "rejected",
    "expired",
    name="access_request_status",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("role", user_role_enum, nullable=False),
        sa.Column("status", user_status_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "access_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("status", access_request_status_enum, nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=True),
        sa.Column("approved_by", sa.String(length=36), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(op.f("ix_access_requests_email"), "access_requests", ["email"], unique=False)
    op.create_index(op.f("ix_access_requests_status"), "access_requests", ["status"], unique=False)

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("session_token_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_token_hash"),
    )
    op.create_index(op.f("ix_auth_sessions_expires_at"), "auth_sessions", ["expires_at"], unique=False)
    op.create_index(op.f("ix_auth_sessions_user_id"), "auth_sessions", ["user_id"], unique=False)

    op.create_table(
        "chats",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("kind", chat_kind_enum, nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chats_user_id"), "chats", ["user_id"], unique=False)
    op.create_index("ix_chats_user_id_archived", "chats", ["user_id", "is_archived"], unique=False)
    op.create_index("ix_chats_user_id_deleted", "chats", ["user_id", "is_deleted"], unique=False)
    op.create_index("ix_chats_user_id_kind", "chats", ["user_id", "kind"], unique=False)

    op.create_table(
        "encrypted_secrets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("secret_type", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("encrypted_value", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_encrypted_secret_user_name"),
    )
    op.create_index(op.f("ix_encrypted_secrets_secret_type"), "encrypted_secrets", ["secret_type"], unique=False)
    op.create_index(op.f("ix_encrypted_secrets_user_id"), "encrypted_secrets", ["user_id"], unique=False)

    op.create_table(
        "messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("chat_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("role", message_role_enum, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_messages_chat_id"), "messages", ["chat_id"], unique=False)
    op.create_index(op.f("ix_messages_created_at"), "messages", ["created_at"], unique=False)
    op.create_index(op.f("ix_messages_user_id"), "messages", ["user_id"], unique=False)

    op.create_table(
        "file_meta",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("chat_id", sa.String(length=36), nullable=True),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("extracted_text_status", sa.String(length=64), nullable=True),
        sa.Column("extracted_text_meta", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_file_meta_chat_id"), "file_meta", ["chat_id"], unique=False)
    op.create_index(op.f("ix_file_meta_created_at"), "file_meta", ["created_at"], unique=False)
    op.create_index(op.f("ix_file_meta_user_id"), "file_meta", ["user_id"], unique=False)

    op.create_table(
        "usage_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("chat_id", sa.String(length=36), nullable=True),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_usage_records_chat_id"), "usage_records", ["chat_id"], unique=False)
    op.create_index(op.f("ix_usage_records_created_at"), "usage_records", ["created_at"], unique=False)
    op.create_index(op.f("ix_usage_records_kind"), "usage_records", ["kind"], unique=False)
    op.create_index(op.f("ix_usage_records_user_id"), "usage_records", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_usage_records_user_id"), table_name="usage_records")
    op.drop_index(op.f("ix_usage_records_kind"), table_name="usage_records")
    op.drop_index(op.f("ix_usage_records_created_at"), table_name="usage_records")
    op.drop_index(op.f("ix_usage_records_chat_id"), table_name="usage_records")
    op.drop_table("usage_records")

    op.drop_index(op.f("ix_file_meta_user_id"), table_name="file_meta")
    op.drop_index(op.f("ix_file_meta_created_at"), table_name="file_meta")
    op.drop_index(op.f("ix_file_meta_chat_id"), table_name="file_meta")
    op.drop_table("file_meta")

    op.drop_index(op.f("ix_messages_user_id"), table_name="messages")
    op.drop_index(op.f("ix_messages_created_at"), table_name="messages")
    op.drop_index(op.f("ix_messages_chat_id"), table_name="messages")
    op.drop_table("messages")

    op.drop_index(op.f("ix_encrypted_secrets_user_id"), table_name="encrypted_secrets")
    op.drop_index(op.f("ix_encrypted_secrets_secret_type"), table_name="encrypted_secrets")
    op.drop_table("encrypted_secrets")

    op.drop_index("ix_chats_user_id_kind", table_name="chats")
    op.drop_index("ix_chats_user_id_deleted", table_name="chats")
    op.drop_index("ix_chats_user_id_archived", table_name="chats")
    op.drop_index(op.f("ix_chats_user_id"), table_name="chats")
    op.drop_table("chats")

    op.drop_index(op.f("ix_auth_sessions_user_id"), table_name="auth_sessions")
    op.drop_index(op.f("ix_auth_sessions_expires_at"), table_name="auth_sessions")
    op.drop_table("auth_sessions")

    op.drop_index(op.f("ix_access_requests_status"), table_name="access_requests")
    op.drop_index(op.f("ix_access_requests_email"), table_name="access_requests")
    op.drop_table("access_requests")

    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
