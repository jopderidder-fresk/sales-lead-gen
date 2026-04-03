"""drop_redundant_ix_companies_domain

The unique constraint on companies.domain already creates an implicit index.
The separate non-unique ix_companies_domain index is redundant overhead.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-26 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_companies_domain", table_name="companies")


def downgrade() -> None:
    op.create_index("ix_companies_domain", "companies", ["domain"])
