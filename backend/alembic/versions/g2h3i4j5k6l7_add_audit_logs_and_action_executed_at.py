"""add audit_logs table and action_executed_at to signals

Revision ID: g2h3i4j5k6l7
Revises: f1a2b3c4d5e6
Create Date: 2026-03-26 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "g2h3i4j5k6l7"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    audit_log_target_enum = sa.Enum(
        "clickup", "slack", "enrichment",
        name="auditlogtarget",
    )
    audit_log_status_enum = sa.Enum(
        "success", "failure",
        name="auditlogstatus",
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "signal_id",
            sa.Integer(),
            sa.ForeignKey("signals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "action_type",
            postgresql.ENUM(
                "notify_immediate", "notify_digest", "enrich_further", "ignore",
                name="signalaction",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("target", audit_log_target_enum, nullable=False),
        sa.Column("target_id", sa.String(255), nullable=True),
        sa.Column("status", audit_log_status_enum, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_audit_logs_signal_id", "audit_logs", ["signal_id"])
    op.create_index("ix_audit_logs_action_type", "audit_logs", ["action_type"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    op.add_column(
        "signals",
        sa.Column("action_executed_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("signals", "action_executed_at")

    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action_type", table_name="audit_logs")
    op.drop_index("ix_audit_logs_signal_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    sa.Enum(name="auditlogtarget").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="auditlogstatus").drop(op.get_bind(), checkfirst=True)
