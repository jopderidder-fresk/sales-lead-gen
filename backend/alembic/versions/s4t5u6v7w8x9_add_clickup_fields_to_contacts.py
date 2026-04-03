"""add clickup_task_id and clickup_task_url to contacts

Revision ID: s4t5u6v7w8x9
Revises: r3s4t5u6v7w8
Create Date: 2026-04-01 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "s4t5u6v7w8x9"
down_revision: str | None = "r3s4t5u6v7w8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "contacts",
        sa.Column("clickup_task_id", sa.String(100), nullable=True),
    )
    op.add_column(
        "contacts",
        sa.Column("clickup_task_url", sa.String(500), nullable=True),
    )
    op.create_index("ix_contacts_clickup_task_id", "contacts", ["clickup_task_id"])


def downgrade() -> None:
    op.drop_index("ix_contacts_clickup_task_id", table_name="contacts")
    op.drop_column("contacts", "clickup_task_url")
    op.drop_column("contacts", "clickup_task_id")
