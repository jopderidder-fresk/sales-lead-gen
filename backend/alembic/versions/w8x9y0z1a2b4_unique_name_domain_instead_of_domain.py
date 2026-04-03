"""Replace domain-only unique constraint with (name, domain) composite.

Different KVK entities (e.g. subsidiaries) may share the same parent domain
but are separate business units with distinct names.

Revision ID: w8x9y0z1a2b4
Revises: w8x9y0z1a2b3
Create Date: 2026-04-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "w8x9y0z1a2b4"
down_revision: str | None = "w8x9y0z1a2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_companies_domain", "companies", type_="unique")
    op.create_index("ix_companies_domain", "companies", ["domain"])
    op.create_unique_constraint(
        "uq_companies_name_domain", "companies", ["name", "domain"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_companies_name_domain", "companies", type_="unique")
    op.drop_index("ix_companies_domain", table_name="companies")
    op.create_unique_constraint("uq_companies_domain", "companies", ["domain"])
