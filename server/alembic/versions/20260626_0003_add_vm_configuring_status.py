"""add vm configuring status

Revision ID: 20260626_0003
Revises: 20260618_0001
Create Date: 2026-06-26
"""

from alembic import op


revision = "20260626_0003"
down_revision = "20260618_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE vm_status ADD VALUE IF NOT EXISTS 'configuring' AFTER 'creating'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values safely without recreating
    # the type and rewriting dependent columns. Keep the value on downgrade.
    pass
