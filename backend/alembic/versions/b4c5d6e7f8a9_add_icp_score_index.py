"""Add index on companies.icp_score for sorting performance.

Revision ID: b4c5d6e7f8a9
Revises: 00a8dbe281c1
Create Date: 2026-04-07
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b4c5d6e7f8a9"
down_revision: str | None = "00a8dbe281c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_companies_icp_score", "companies", ["icp_score"])


def downgrade() -> None:
    op.drop_index("ix_companies_icp_score", table_name="companies")
