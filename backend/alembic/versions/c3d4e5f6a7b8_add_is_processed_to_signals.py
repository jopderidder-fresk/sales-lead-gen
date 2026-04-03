"""add_is_processed_to_signals

Add is_processed boolean column and index to the signals table so the
LLM intelligence pipeline can efficiently query unprocessed signals.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-26 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "signals",
        sa.Column("is_processed", sa.Boolean(), server_default="false", nullable=False),
    )
    op.create_index("ix_signals_is_processed", "signals", ["is_processed"])


def downgrade() -> None:
    op.drop_index("ix_signals_is_processed", table_name="signals")
    op.drop_column("signals", "is_processed")
