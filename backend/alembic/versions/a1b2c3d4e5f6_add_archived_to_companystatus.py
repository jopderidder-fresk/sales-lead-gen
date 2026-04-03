"""add_archived_to_companystatus

Revision ID: a1b2c3d4e5f6
Revises: ef6ca7893d4e
Create Date: 2026-03-25 14:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "ef6ca7893d4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE companystatus ADD VALUE IF NOT EXISTS 'archived'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from an enum type.
    # A full enum recreation would be needed, which is intentionally omitted
    # to avoid data loss if rows reference 'archived'.
    pass
