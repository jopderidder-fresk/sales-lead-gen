"""add discovery_jobs table

Revision ID: f1a2b3c4d5e6
Revises: 29174d634a2d
Create Date: 2026-03-26 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "29174d634a2d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _status_enum = sa.Enum(
        "pending", "running", "completed", "failed",
        name="discoveryjobstatus",
    )

    op.create_table(
        "discovery_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("status", _status_enum, nullable=False, server_default="pending"),
        sa.Column("trigger", sa.String(), nullable=False, server_default="manual"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("companies_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("companies_added", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("companies_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("results", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("celery_task_id", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_discovery_jobs_status", "discovery_jobs", ["status"])
    op.create_index("ix_discovery_jobs_created_at", "discovery_jobs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_discovery_jobs_created_at", table_name="discovery_jobs")
    op.drop_index("ix_discovery_jobs_status", table_name="discovery_jobs")
    op.drop_table("discovery_jobs")
    sa.Enum(name="discoveryjobstatus").drop(op.get_bind(), checkfirst=True)
