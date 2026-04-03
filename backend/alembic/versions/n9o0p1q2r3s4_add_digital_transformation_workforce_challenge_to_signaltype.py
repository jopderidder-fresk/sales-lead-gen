"""add digital_transformation and workforce_challenge to signaltype

Revision ID: n9o0p1q2r3s4
Revises: m8n9o0p1q2r3
Create Date: 2026-03-27 12:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "n9o0p1q2r3s4"
down_revision: str | None = "m8n9o0p1q2r3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add fresk.digital ICP signal types to signaltype enum."""
    op.execute("ALTER TYPE signaltype ADD VALUE IF NOT EXISTS 'digital_transformation'")
    op.execute("ALTER TYPE signaltype ADD VALUE IF NOT EXISTS 'workforce_challenge'")


def downgrade() -> None:
    """Downgrade — PostgreSQL does not support removing enum values."""
    pass
