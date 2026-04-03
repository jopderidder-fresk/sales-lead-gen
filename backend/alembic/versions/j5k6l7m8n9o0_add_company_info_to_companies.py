"""Add company_info JSONB column to companies table.

Revision ID: j5k6l7m8n9o0
Revises: i4j5k6l7m8n9
Create Date: 2026-03-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "j5k6l7m8n9o0"
down_revision = "i4j5k6l7m8n9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("company_info", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("companies", "company_info")
