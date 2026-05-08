"""merge heads for postgres migration stage 1.0.3

Revision ID: 20260508_04
Revises: 20260508_01, 20260508_02, 20260508_03
Create Date: 2026-05-08 19:35:00
"""

from __future__ import annotations


revision = "20260508_04"
down_revision = ("20260508_01", "20260508_02", "20260508_03")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
