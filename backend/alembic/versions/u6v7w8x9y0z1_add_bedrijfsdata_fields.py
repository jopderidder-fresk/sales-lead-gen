"""Add bedrijfsdata fields to companies table.

Revision ID: u6v7w8x9y0z1
Revises: t5u6v7w8x9y0
Create Date: 2026-04-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "u6v7w8x9y0z1"
down_revision: str | None = "t5u6v7w8x9y0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("kvk_number", sa.String(20), nullable=True))
    op.add_column("companies", sa.Column("phone", sa.String(50), nullable=True))
    op.add_column("companies", sa.Column("email", sa.String(255), nullable=True))
    op.add_column("companies", sa.Column("website_url", sa.String(500), nullable=True))
    op.add_column("companies", sa.Column("address", sa.String(255), nullable=True))
    op.add_column("companies", sa.Column("postal_code", sa.String(20), nullable=True))
    op.add_column("companies", sa.Column("city", sa.String(100), nullable=True))
    op.add_column("companies", sa.Column("province", sa.String(100), nullable=True))
    op.add_column("companies", sa.Column("country", sa.String(10), nullable=True))
    op.add_column("companies", sa.Column("founded_year", sa.Integer(), nullable=True))
    op.add_column("companies", sa.Column("employee_count", sa.Integer(), nullable=True))
    op.add_column("companies", sa.Column("organization_type", sa.String(100), nullable=True))
    op.add_column("companies", sa.Column("facebook_url", sa.String(500), nullable=True))
    op.add_column("companies", sa.Column("twitter_url", sa.String(500), nullable=True))
    op.add_column("companies", sa.Column("bedrijfsdata", postgresql.JSONB(), nullable=True))
    op.create_index("ix_companies_kvk_number", "companies", ["kvk_number"])


def downgrade() -> None:
    op.drop_index("ix_companies_kvk_number", table_name="companies")
    op.drop_column("companies", "bedrijfsdata")
    op.drop_column("companies", "twitter_url")
    op.drop_column("companies", "facebook_url")
    op.drop_column("companies", "organization_type")
    op.drop_column("companies", "employee_count")
    op.drop_column("companies", "founded_year")
    op.drop_column("companies", "country")
    op.drop_column("companies", "province")
    op.drop_column("companies", "city")
    op.drop_column("companies", "postal_code")
    op.drop_column("companies", "address")
    op.drop_column("companies", "website_url")
    op.drop_column("companies", "email")
    op.drop_column("companies", "phone")
    op.drop_column("companies", "kvk_number")
