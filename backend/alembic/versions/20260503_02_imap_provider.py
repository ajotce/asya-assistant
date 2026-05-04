"""add imap provider to integration enums

Revision ID: 20260503_02
Revises: 20260503_01
Create Date: 2026-05-03 23:25:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260503_02"
down_revision = "20260503_01"
branch_labels = None
depends_on = None


old_integration_provider_enum = sa.Enum(
    "linear",
    "google_calendar",
    "todoist",
    "gmail",
    "google_drive",
    "telegram",
    "bitrix24",
    "yandex_disk",
    "onedrive",
    "icloud_drive",
    name="integration_provider",
    native_enum=False,
)

new_integration_provider_enum = sa.Enum(
    "linear",
    "google_calendar",
    "todoist",
    "gmail",
    "imap",
    "google_drive",
    "telegram",
    "bitrix24",
    "yandex_disk",
    "onedrive",
    "icloud_drive",
    name="integration_provider",
    native_enum=False,
)


def upgrade() -> None:
    with op.batch_alter_table("integration_connections", recreate="always") as batch_op:
        batch_op.alter_column(
            "provider",
            existing_type=old_integration_provider_enum,
            type_=new_integration_provider_enum,
            existing_nullable=False,
        )
    with op.batch_alter_table("oauth_states", recreate="always") as batch_op:
        batch_op.alter_column(
            "provider",
            existing_type=old_integration_provider_enum,
            type_=new_integration_provider_enum,
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("oauth_states", recreate="always") as batch_op:
        batch_op.alter_column(
            "provider",
            existing_type=new_integration_provider_enum,
            type_=old_integration_provider_enum,
            existing_nullable=False,
        )
    with op.batch_alter_table("integration_connections", recreate="always") as batch_op:
        batch_op.alter_column(
            "provider",
            existing_type=new_integration_provider_enum,
            type_=old_integration_provider_enum,
            existing_nullable=False,
        )
