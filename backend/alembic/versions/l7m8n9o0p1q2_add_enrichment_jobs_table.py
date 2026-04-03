"""add enrichment_jobs table

Revision ID: l7m8n9o0p1q2
Revises: k6l7m8n9o0p1
Create Date: 2026-03-26 21:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "l7m8n9o0p1q2"
down_revision: str | None = "k6l7m8n9o0p1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "enrichment_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "running", "completed", "failed", name="enrichmentjobstatus"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_enrichment_jobs_company_id", "enrichment_jobs", ["company_id"])
    op.create_index("ix_enrichment_jobs_status", "enrichment_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_enrichment_jobs_status", table_name="enrichment_jobs")
    op.drop_index("ix_enrichment_jobs_company_id", table_name="enrichment_jobs")
    op.drop_table("enrichment_jobs")
    op.execute("DROP TYPE IF EXISTS enrichmentjobstatus")
