"""Add linkedin_last_scraped_at to companies.

Tracks per-company LinkedIn scrape timestamps for priority-ranked
daily rotation instead of one global interval.

Revision ID: 00a8dbe281c1
Revises: z1a2b3c4d5e6
Create Date: 2026-04-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "00a8dbe281c1"
down_revision: str | None = "z1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "companies",
        sa.Column("linkedin_last_scraped_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("companies", "linkedin_last_scraped_at")
