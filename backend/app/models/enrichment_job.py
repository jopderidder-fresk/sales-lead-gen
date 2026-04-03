from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import EnrichmentJobStatus


class EnrichmentJob(Base):
    __tablename__ = "enrichment_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    status: Mapped[EnrichmentJobStatus] = mapped_column(
        Enum(EnrichmentJobStatus, values_callable=lambda e: [x.value for x in e]),
        default=EnrichmentJobStatus.PENDING,
    )
    started_at: Mapped[datetime | None] = mapped_column()
    completed_at: Mapped[datetime | None] = mapped_column()
    result_summary: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="enrichment_jobs")  # noqa: F821

    __table_args__ = (
        Index("ix_enrichment_jobs_company_id", "company_id"),
        Index("ix_enrichment_jobs_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<EnrichmentJob(id={self.id}, status={self.status!r}, company_id={self.company_id})>"
