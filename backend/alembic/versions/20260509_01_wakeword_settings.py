"""add wakeword settings to user_settings

Revision ID: 20260509_01
Revises: 20260508_02
Create Date: 2026-05-09 12:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260509_01"
down_revision: Union[str, None] = "20260508_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("wakeword_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "user_settings",
        sa.Column("wakeword_phrase", sa.String(length=32), nullable=False, server_default="ася"),
    )
    op.add_column(
        "user_settings",
        sa.Column("wakeword_sensitivity", sa.Float(), nullable=False, server_default=sa.text("0.5")),
    )


def downgrade() -> None:
    op.drop_column("user_settings", "wakeword_sensitivity")
    op.drop_column("user_settings", "wakeword_phrase")
    op.drop_column("user_settings", "wakeword_enabled")
