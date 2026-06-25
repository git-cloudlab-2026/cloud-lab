"""add failed request status if missing

Revision ID: 20260623_0002
Revises: 20260618_0001
Create Date: 2026-06-23
"""

from alembic import op


revision = "20260623_0002"
down_revision = "20260618_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE request_status ADD VALUE IF NOT EXISTS 'failed'")


def downgrade() -> None:
    # PostgreSQL ne permet pas de retirer proprement une valeur d'enum sans recréer le type.
    pass
