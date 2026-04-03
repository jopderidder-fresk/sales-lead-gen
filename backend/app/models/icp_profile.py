from datetime import datetime

from sqlalchemy import String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ICPProfile(Base):
    __tablename__ = "icp_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    industry_filter: Mapped[list[str] | None] = mapped_column(JSONB)
    size_filter: Mapped[dict[str, int] | None] = mapped_column(JSONB)
    geo_filter: Mapped[dict[str, list[str]] | None] = mapped_column(JSONB)
    tech_filter: Mapped[list[str] | None] = mapped_column(JSONB)
    negative_filters: Mapped[dict[str, list[str]] | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    def __repr__(self) -> str:
        return f"<ICPProfile(id={self.id}, name={self.name!r}, active={self.is_active})>"
