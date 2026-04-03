"""Add 'crm' value to auditlogtarget enum.

The Python AuditLogTarget enum includes CRM = "crm" but the database enum
was created without it, causing INSERT failures in action_orchestrator.

Revision ID: w8x9y0z1a2b3
Revises: v7w8x9y0z1a2
Create Date: 2026-04-01
"""

from collections.abc import Sequence

from alembic import op

revision: str = "w8x9y0z1a2b3"
down_revision: str | None = "v7w8x9y0z1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE auditlogtarget ADD VALUE IF NOT EXISTS 'crm'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values; no-op.
    pass
