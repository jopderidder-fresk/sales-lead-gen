from datetime import datetime

from sqlalchemy import Enum, Index, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import DiscoveryJobStatus


class DiscoveryJob(Base):
    __tablename__ = "discovery_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[DiscoveryJobStatus] = mapped_column(
        Enum(DiscoveryJobStatus, values_callable=lambda e: [x.value for x in e]),
        default=DiscoveryJobStatus.PENDING,
    )
    trigger: Mapped[str] = mapped_column(default="manual")
    started_at: Mapped[datetime | None] = mapped_column()
    completed_at: Mapped[datetime | None] = mapped_column()
    companies_found: Mapped[int] = mapped_column(default=0)
    companies_added: Mapped[int] = mapped_column(default=0)
    companies_skipped: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    results: Mapped[dict | None] = mapped_column(JSONB, default=None)
    celery_task_id: Mapped[str | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        Index("ix_discovery_jobs_status", "status"),
        Index("ix_discovery_jobs_created_at", "created_at"),
    )

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def __repr__(self) -> str:
        return f"<DiscoveryJob(id={self.id}, status={self.status!r})>"
