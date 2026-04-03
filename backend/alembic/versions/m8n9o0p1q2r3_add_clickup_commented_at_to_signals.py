"""add clickup_commented_at to signals

Revision ID: m8n9o0p1q2r3
Revises: l7m8n9o0p1q2
Create Date: 2026-03-26 22:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "m8n9o0p1q2r3"
down_revision: str | None = "l7m8n9o0p1q2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "signals",
        sa.Column("clickup_commented_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("signals", "clickup_commented_at")
