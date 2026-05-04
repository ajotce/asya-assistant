"""extend integration providers for file storage v0.5

Revision ID: 20260503_01
Revises: 20260502_08
Create Date: 2026-05-03 22:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260503_01"
down_revision = "20260502_08"
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
    name="integration_provider",
    native_enum=False,
)

new_integration_provider_enum = sa.Enum(
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
