"""add source_title to signals

Revision ID: i4j5k6l7m8n9
Revises: g2h3i4j5k6l7
Create Date: 2026-03-26 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "i4j5k6l7m8n9"
down_revision: str | None = "g2h3i4j5k6l7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "signals",
        sa.Column("source_title", sa.String(512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("signals", "source_title")
