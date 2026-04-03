"""Widen industry column from VARCHAR(255) to TEXT.

Bedrijfsdata branches_kvk values are comma-separated lists that regularly
exceed 255 characters (up to ~1400 chars observed).

Revision ID: v7w8x9y0z1a2
Revises: u6v7w8x9y0z1
Create Date: 2026-04-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v7w8x9y0z1a2"
down_revision: str | None = "u6v7w8x9y0z1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "companies",
        "industry",
        existing_type=sa.String(255),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "companies",
        "industry",
        existing_type=sa.Text(),
        type_=sa.String(255),
        existing_nullable=True,
    )
