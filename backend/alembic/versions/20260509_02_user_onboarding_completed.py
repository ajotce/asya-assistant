"""add onboarding_completed flag to users

Revision ID: 20260509_02
Revises: 20260509_01
Create Date: 2026-05-09 15:05:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260509_02"
down_revision: str | Sequence[str] | None = "20260509_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("onboarding_completed", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("users", "onboarding_completed")
