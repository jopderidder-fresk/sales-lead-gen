"""Add monitor and monitor_pinned columns to companies.

Companies with an ICP score >= 85 will have monitor auto-enabled.
The monitor_pinned flag lets users manually override the automatic behavior.
LinkedIn batch scraping is gated on monitor=True.

Revision ID: z1a2b3c4d5e6
Revises: y0z1a2b3c4d5
Create Date: 2026-04-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "z1a2b3c4d5e6"
down_revision: str | None = "y0z1a2b3c4d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "companies",
        sa.Column("monitor", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "companies",
        sa.Column("monitor_pinned", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_companies_monitor", "companies", ["monitor"])

    # Auto-enable monitor for existing companies with icp_score >= 85
    op.execute(
        "UPDATE companies SET monitor = true WHERE icp_score >= 85 AND status != 'archived'"
    )


def downgrade() -> None:
    op.drop_index("ix_companies_monitor", table_name="companies")
    op.drop_column("companies", "monitor_pinned")
    op.drop_column("companies", "monitor")
