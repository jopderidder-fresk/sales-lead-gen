"""Add prompt_configs table for configurable LLM prompt parts.

Stores signal type definitions, company identity, decision-maker roles,
and other configurable prompt sections as JSONB documents.

Revision ID: x9y0z1a2b3c4
Revises: w8x9y0z1a2b4
Create Date: 2026-04-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "x9y0z1a2b3c4"
down_revision: str = "w8x9y0z1a2b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "prompt_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("config_key", sa.String(80), nullable=False),
        sa.Column("config_value", postgresql.JSONB(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_prompt_configs_config_key", "prompt_configs", ["config_key"], unique=True)

    # Seed default rows so the system works immediately after migration.
    op.execute(
        sa.text(
            """
            INSERT INTO prompt_configs (config_key, config_value, description) VALUES
            (
                'signal_type_definitions',
                CAST(:signal_types AS jsonb),
                'Signal types shown in the classification prompt'
            ),
            (
                'company_identity',
                CAST(:company_identity AS jsonb),
                'Company name and tagline used across all prompts'
            ),
            (
                'decision_maker_roles',
                CAST(:dm_roles AS jsonb),
                'Roles flagged as decision-makers in contact extraction'
            )
            """
        ).bindparams(
            signal_types='[{"key":"hiring_surge","description":"Multiple open roles for field service professionals (monteurs, engineers, inspecteurs, service technici, planners) or rapid headcount growth in operations","relevance_hints":"Look for monteurs, engineers, inspecteurs, werkvoorbereiders, planners"},{"key":"technology_adoption","description":"Migrating to or adopting new operational systems (ERP, CRM, FSM), cloud infrastructure, IoT platforms, or major tooling changes","relevance_hints":null},{"key":"digital_transformation","description":"Announcing digital transformation initiatives, innovation programmes, operational excellence projects, legacy system replacements, or AI/data strategy","relevance_hints":null},{"key":"workforce_challenge","description":"Mentions of personnel shortages, aging workforce, knowledge retention issues, difficulty finding qualified technicians/monteurs, or high employee turnover","relevance_hints":null},{"key":"funding_round","description":"Investment, acquisition, or capital announcement enabling growth","relevance_hints":null},{"key":"leadership_change","description":"New CIO, CDO, COO, or VP Operations/IT/Innovation appointment or departure","relevance_hints":null},{"key":"expansion","description":"New offices, service regions, entering new markets or geographies","relevance_hints":null},{"key":"partnership","description":"Strategic partnerships, integrations, or joint ventures with technology providers","relevance_hints":null},{"key":"product_launch","description":"New product, service proposition, or major feature release","relevance_hints":null},{"key":"no_signal","description":"Content does not indicate buying intent (e.g. team events, culture posts, generic news)","relevance_hints":null}]',
            company_identity='{"name":"fresk.digital","tagline":"a digital product studio that builds intelligent tools for field service professionals and frontline knowledge workers"}',
            dm_roles='["COO","CIO","CDO","CTO","CEO","VP Operations","VP IT","VP Digital","VP Innovation","Director Operations","Director IT","Director Digital","Director Innovation","Hoofd Operations","Hoofd IT","Hoofd Digital","Hoofd Innovation","HR/Employee Experience","Divisie-/Afdelingsmanager Operations","Innovatiemanager"]',
        ),
    )


def downgrade() -> None:
    op.drop_index("ix_prompt_configs_config_key", table_name="prompt_configs")
    op.drop_table("prompt_configs")
