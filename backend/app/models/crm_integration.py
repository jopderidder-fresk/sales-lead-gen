from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CRMIntegration(Base):
    __tablename__ = "crm_integrations"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), unique=True,
    )
    provider: Mapped[str] = mapped_column(String(50))
    external_id: Mapped[str] = mapped_column(String(255))
    external_url: Mapped[str | None] = mapped_column(String(500))
    external_status: Mapped[str | None] = mapped_column(String(100))
    synced_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    company: Mapped["Company"] = relationship(back_populates="crm_integration")  # noqa: F821

    __table_args__ = (
        # ix_crm_integrations_company_id omitted — unique=True on company_id
        # already creates an index.
        Index("ix_crm_integrations_provider_external_id", "provider", "external_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<CRMIntegration(id={self.id}, provider={self.provider!r}, "
            f"company_id={self.company_id}, external_id={self.external_id!r})>"
        )
