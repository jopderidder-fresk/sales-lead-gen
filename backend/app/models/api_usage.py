from datetime import datetime
from decimal import Decimal

from sqlalchemy import Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class APIUsage(Base):
    __tablename__ = "api_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(100))
    endpoint: Mapped[str] = mapped_column(String(500))
    credits_used: Mapped[float | None] = mapped_column()
    tokens_used: Mapped[int | None] = mapped_column()
    cost_estimate: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    timestamp: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        Index("ix_api_usage_provider", "provider"),
        Index("ix_api_usage_timestamp", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<APIUsage(id={self.id}, provider={self.provider!r}, cost={self.cost_estimate})>"
