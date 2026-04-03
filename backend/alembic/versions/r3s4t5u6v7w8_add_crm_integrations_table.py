"""add crm_integrations table and migrate clickup data

Revision ID: r3s4t5u6v7w8
Revises: q2r3s4t5u6v7
Create Date: 2026-03-27 16:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "r3s4t5u6v7w8"
down_revision: str | None = "q2r3s4t5u6v7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create crm_integrations table
    op.create_table(
        "crm_integrations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("external_url", sa.String(500), nullable=True),
        sa.Column("external_status", sa.String(100), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_crm_integrations_company_id", "crm_integrations", ["company_id"])
    op.create_index(
        "ix_crm_integrations_provider_external_id",
        "crm_integrations",
        ["provider", "external_id"],
    )

    # 2. Migrate existing ClickUp data from companies table
    op.execute(
        """
        INSERT INTO crm_integrations (company_id, provider, external_id, external_url, external_status, created_at, updated_at)
        SELECT id, 'clickup', clickup_task_id, clickup_task_url, clickup_status, created_at, updated_at
        FROM companies
        WHERE clickup_task_id IS NOT NULL
        """
    )

    # 3. Rename signals.clickup_commented_at → crm_commented_at
    op.alter_column("signals", "clickup_commented_at", new_column_name="crm_commented_at")

    # Note: old clickup_* columns on companies are kept for now (backwards compat).
    # They will be dropped in a follow-up migration after verification.


def downgrade() -> None:
    op.alter_column("signals", "crm_commented_at", new_column_name="clickup_commented_at")
    op.drop_index("ix_crm_integrations_provider_external_id", table_name="crm_integrations")
    op.drop_index("ix_crm_integrations_company_id", table_name="crm_integrations")
    op.drop_table("crm_integrations")
