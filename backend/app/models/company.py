from datetime import datetime

from sqlalchemy import Boolean, Enum, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import CompanyStatus


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    domain: Mapped[str] = mapped_column(String(255))
    industry: Mapped[str | None] = mapped_column(Text)
    size: Mapped[str | None] = mapped_column(String(100))
    location: Mapped[str | None] = mapped_column(String(255))
    icp_score: Mapped[float | None] = mapped_column()
    lead_score: Mapped[float | None] = mapped_column()
    score_breakdown: Mapped[dict | None] = mapped_column(JSONB)
    score_updated_at: Mapped[datetime | None] = mapped_column()
    company_info: Mapped[dict | None] = mapped_column(JSONB)
    linkedin_url: Mapped[str | None] = mapped_column(String(500))
    kvk_number: Mapped[str | None] = mapped_column(String(20))
    phone: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(255))
    website_url: Mapped[str | None] = mapped_column(String(500))
    address: Mapped[str | None] = mapped_column(String(255))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    city: Mapped[str | None] = mapped_column(String(100))
    province: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(10))
    founded_year: Mapped[int | None] = mapped_column()
    employee_count: Mapped[int | None] = mapped_column()
    organization_type: Mapped[str | None] = mapped_column(String(100))
    facebook_url: Mapped[str | None] = mapped_column(String(500))
    twitter_url: Mapped[str | None] = mapped_column(String(500))
    bedrijfsdata: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[CompanyStatus] = mapped_column(Enum(CompanyStatus, values_callable=lambda e: [x.value for x in e]), default=CompanyStatus.DISCOVERED)
    clickup_task_id: Mapped[str | None] = mapped_column(String(100))
    clickup_task_url: Mapped[str | None] = mapped_column(String(500))
    clickup_status: Mapped[str | None] = mapped_column(String(100))
    monitor: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    monitor_pinned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    slack_notified_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    # Relationships
    contacts: Mapped[list["Contact"]] = relationship(back_populates="company")  # noqa: F821
    signals: Mapped[list["Signal"]] = relationship(back_populates="company")  # noqa: F821
    scrape_jobs: Mapped[list["ScrapeJob"]] = relationship(back_populates="company")  # noqa: F821
    enrichment_jobs: Mapped[list["EnrichmentJob"]] = relationship(back_populates="company")  # noqa: F821
    crm_integration: Mapped["CRMIntegration | None"] = relationship(back_populates="company", uselist=False)  # noqa: F821

    __table_args__ = (
        Index("ix_companies_status", "status"),
        Index("ix_companies_lead_score", "lead_score"),
        Index("ix_companies_kvk_number", "kvk_number"),
        Index("ix_companies_domain", "domain"),
        Index("ix_companies_monitor", "monitor"),
        Index("uq_companies_name_domain", "name", "domain", unique=True),
    )

    def __repr__(self) -> str:
        return f"<Company(id={self.id}, name={self.name!r}, domain={self.domain!r})>"
