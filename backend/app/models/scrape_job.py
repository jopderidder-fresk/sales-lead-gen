from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import ScrapeJobStatus


class ScrapeJob(Base):
    __tablename__ = "scrape_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    target_url: Mapped[str] = mapped_column(String(2048))
    status: Mapped[ScrapeJobStatus] = mapped_column(Enum(ScrapeJobStatus, values_callable=lambda e: [x.value for x in e]), default=ScrapeJobStatus.PENDING)
    started_at: Mapped[datetime | None] = mapped_column()
    completed_at: Mapped[datetime | None] = mapped_column()
    pages_scraped: Mapped[int | None] = mapped_column()
    credits_used: Mapped[float | None] = mapped_column()
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="scrape_jobs")  # noqa: F821

    __table_args__ = (
        Index("ix_scrape_jobs_company_id", "company_id"),
        Index("ix_scrape_jobs_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<ScrapeJob(id={self.id}, status={self.status!r}, company_id={self.company_id})>"
