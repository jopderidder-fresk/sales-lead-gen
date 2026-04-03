"""Persistent storage for configurable prompt parts (signal definitions, etc.)."""

from datetime import datetime

from typing import Any

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PromptConfig(Base):
    """DB-backed configuration for LLM prompt templates.

    Each row holds a JSON document keyed by ``config_key``.  Known keys:

    * ``signal_type_definitions`` — list of signal types with descriptions
    * ``company_identity`` — company name + tagline used in prompts
    * ``decision_maker_roles`` — roles considered decision-makers in contact extraction
    """

    __tablename__ = "prompt_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    config_key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    config_value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<PromptConfig(key={self.config_key!r})>"
