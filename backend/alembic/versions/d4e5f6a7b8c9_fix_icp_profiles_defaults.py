"""fix_icp_profiles_defaults

Fix server_default for is_active from true to false (new profiles should
start inactive) and add a unique partial index to guarantee at most one
active ICP profile at the database level.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-26 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fix default: new profiles should start inactive
    op.alter_column(
        "icp_profiles",
        "is_active",
        server_default=sa.text("false"),
    )

    # Ensure at most one active profile at the DB level.
    # The index on the constant TRUE expression means only one row can have is_active = true.
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX ix_icp_profiles_single_active "
            "ON icp_profiles ((true)) WHERE is_active = true"
        )
    )


def downgrade() -> None:
    op.drop_index("ix_icp_profiles_single_active", table_name="icp_profiles")
    op.alter_column(
        "icp_profiles",
        "is_active",
        server_default=sa.text("true"),
    )
