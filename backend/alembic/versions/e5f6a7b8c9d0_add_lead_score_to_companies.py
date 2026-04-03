"""add_lead_score_to_companies

Add lead_score, score_breakdown, and score_updated_at columns to the
companies table for the Lead Scoring Framework (LP-027).

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-03-26 16:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("lead_score", sa.Float(), nullable=True))
    op.add_column("companies", sa.Column("score_breakdown", postgresql.JSONB(), nullable=True))
    op.add_column("companies", sa.Column("score_updated_at", sa.DateTime(), nullable=True))
    op.create_index("ix_companies_lead_score", "companies", ["lead_score"])


def downgrade() -> None:
    op.drop_index("ix_companies_lead_score", table_name="companies")
    op.drop_column("companies", "score_updated_at")
    op.drop_column("companies", "score_breakdown")
    op.drop_column("companies", "lead_score")
