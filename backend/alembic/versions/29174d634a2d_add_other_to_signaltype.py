"""add_other_to_signaltype

Revision ID: 29174d634a2d
Revises: e5f6a7b8c9d0
Create Date: 2026-03-26 12:36:16.421427

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '29174d634a2d'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add 'other' value to signaltype enum."""
    op.execute("ALTER TYPE signaltype ADD VALUE IF NOT EXISTS 'other'")


def downgrade() -> None:
    """Downgrade — PostgreSQL does not support removing enum values."""
    pass
