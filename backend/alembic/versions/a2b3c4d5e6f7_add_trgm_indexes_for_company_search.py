"""Add pg_trgm GIN indexes on companies.name and companies.domain.

Speeds up ILIKE '%pattern%' searches which previously caused full table scans.

Revision ID: a2b3c4d5e6f7
Revises: b4c5d6e7f8a9
Create Date: 2026-04-07
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a2b3c4d5e6f7"
down_revision: str = "b4c5d6e7f8a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX ix_companies_name_trgm ON companies USING gin (name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_companies_domain_trgm ON companies USING gin (domain gin_trgm_ops)"
    )


def downgrade() -> None:
    op.drop_index("ix_companies_domain_trgm", table_name="companies")
    op.drop_index("ix_companies_name_trgm", table_name="companies")
