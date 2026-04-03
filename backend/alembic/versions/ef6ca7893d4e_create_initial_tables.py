"""create_initial_tables

Revision ID: ef6ca7893d4e
Revises:
Create Date: 2026-03-25 11:56:25.324293

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ef6ca7893d4e"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# --- ENUM types ---
company_status = postgresql.ENUM(
    "discovered", "enriched", "monitoring", "qualified", "pushed",
    name="companystatus", create_type=False,
)
email_status = postgresql.ENUM(
    "verified", "catch-all", "unverified",
    name="emailstatus", create_type=False,
)
signal_type = postgresql.ENUM(
    "hiring_surge", "technology_adoption", "funding_round", "leadership_change",
    "expansion", "partnership", "product_launch", "no_signal",
    name="signaltype", create_type=False,
)
signal_action = postgresql.ENUM(
    "notify_immediate", "notify_digest", "enrich_further", "ignore",
    name="signalaction", create_type=False,
)
scrape_job_status = postgresql.ENUM(
    "pending", "running", "completed", "failed",
    name="scrapejobstatus", create_type=False,
)
user_role = postgresql.ENUM(
    "admin", "user", "viewer",
    name="userrole", create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""
    # Create ENUM types
    company_status.create(op.get_bind(), checkfirst=True)
    email_status.create(op.get_bind(), checkfirst=True)
    signal_type.create(op.get_bind(), checkfirst=True)
    signal_action.create(op.get_bind(), checkfirst=True)
    scrape_job_status.create(op.get_bind(), checkfirst=True)
    user_role.create(op.get_bind(), checkfirst=True)

    # --- companies ---
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("industry", sa.String(255), nullable=True),
        sa.Column("size", sa.String(100), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("icp_score", sa.Float(), nullable=True),
        sa.Column("status", company_status, nullable=False, server_default="discovered"),
        sa.Column("clickup_task_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("domain", name="uq_companies_domain"),
    )
    op.create_index("ix_companies_domain", "companies", ["domain"])
    op.create_index("ix_companies_status", "companies", ["status"])

    # --- contacts ---
    op.create_table(
        "contacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "company_id", sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("email_status", email_status, nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("linkedin_url", sa.String(500), nullable=True),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_contacts_company_id", "contacts", ["company_id"])
    op.create_index("ix_contacts_email", "contacts", ["email"])

    # --- signals ---
    op.create_table(
        "signals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "company_id", sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("source_url", sa.String(2048), nullable=True),
        sa.Column("signal_type", signal_type, nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("llm_summary", sa.Text(), nullable=True),
        sa.Column("raw_content_hash", sa.String(64), nullable=True),
        sa.Column("action_taken", signal_action, nullable=True),
        sa.Column("raw_markdown", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_signals_company_id", "signals", ["company_id"])
    op.create_index("ix_signals_created_at", "signals", ["created_at"])
    op.create_index("ix_signals_signal_type", "signals", ["signal_type"])

    # --- scrape_jobs ---
    op.create_table(
        "scrape_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "company_id", sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("target_url", sa.String(2048), nullable=False),
        sa.Column("status", scrape_job_status, nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("pages_scraped", sa.Integer(), nullable=True),
        sa.Column("credits_used", sa.Float(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_scrape_jobs_company_id", "scrape_jobs", ["company_id"])
    op.create_index("ix_scrape_jobs_status", "scrape_jobs", ["status"])

    # --- icp_profiles ---
    op.create_table(
        "icp_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("industry_filter", postgresql.JSONB(), nullable=True),
        sa.Column("size_filter", postgresql.JSONB(), nullable=True),
        sa.Column("geo_filter", postgresql.JSONB(), nullable=True),
        sa.Column("tech_filter", postgresql.JSONB(), nullable=True),
        sa.Column("negative_filters", postgresql.JSONB(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # --- api_usage ---
    op.create_table(
        "api_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("endpoint", sa.String(500), nullable=False),
        sa.Column("credits_used", sa.Float(), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("cost_estimate", sa.Numeric(10, 4), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_api_usage_provider", "api_usage", ["provider"])
    op.create_index("ix_api_usage_timestamp", "api_usage", ["timestamp"])

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="user"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    # --- updated_at trigger for companies ---
    op.execute(sa.text("""
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """))
    op.execute(sa.text("""
        CREATE TRIGGER trg_companies_updated_at
        BEFORE UPDATE ON companies
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at();
    """))


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_companies_updated_at ON companies"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS set_updated_at()"))

    op.drop_table("users")
    op.drop_table("api_usage")
    op.drop_table("icp_profiles")
    op.drop_table("scrape_jobs")
    op.drop_table("signals")
    op.drop_table("contacts")
    op.drop_table("companies")

    # Drop ENUM types
    user_role.drop(op.get_bind(), checkfirst=True)
    scrape_job_status.drop(op.get_bind(), checkfirst=True)
    signal_action.drop(op.get_bind(), checkfirst=True)
    signal_type.drop(op.get_bind(), checkfirst=True)
    email_status.drop(op.get_bind(), checkfirst=True)
    company_status.drop(op.get_bind(), checkfirst=True)
