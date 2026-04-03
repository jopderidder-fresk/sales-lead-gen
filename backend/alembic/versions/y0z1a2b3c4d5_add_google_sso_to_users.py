"""Add Google SSO fields to users table.

- Add google_id column (unique, nullable) for linking Google accounts
- Make password_hash nullable (SSO users have no password)
- Widen username column to 320 chars (to store email as username for SSO users)

Revision ID: y0z1a2b3c4d5
Revises: x9y0z1a2b3c4
Create Date: 2026-04-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "y0z1a2b3c4d5"
down_revision: str | None = "x9y0z1a2b3c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("google_id", sa.String(255), nullable=True))
    op.create_unique_constraint("uq_users_google_id", "users", ["google_id"])
    op.alter_column("users", "password_hash", existing_type=sa.String(255), nullable=True)
    op.alter_column(
        "users", "username", existing_type=sa.String(100), type_=sa.String(320)
    )


def downgrade() -> None:
    op.alter_column(
        "users", "username", existing_type=sa.String(320), type_=sa.String(100)
    )
    op.alter_column("users", "password_hash", existing_type=sa.String(255), nullable=False)
    op.drop_constraint("uq_users_google_id", "users", type_="unique")
    op.drop_column("users", "google_id")
