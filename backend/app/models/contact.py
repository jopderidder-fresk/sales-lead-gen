from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import EmailStatus


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    title: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(320))
    email_status: Mapped[EmailStatus | None] = mapped_column(Enum(EmailStatus, values_callable=lambda e: [x.value for x in e]))
    phone: Mapped[str | None] = mapped_column(String(50))
    linkedin_url: Mapped[str | None] = mapped_column(String(500))
    source: Mapped[str | None] = mapped_column(String(100))
    confidence_score: Mapped[float | None] = mapped_column()
    clickup_task_id: Mapped[str | None] = mapped_column(String(100))
    clickup_task_url: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="contacts")  # noqa: F821

    __table_args__ = (
        Index("ix_contacts_company_id", "company_id"),
        Index("ix_contacts_email", "email"),
        Index("ix_contacts_clickup_task_id", "clickup_task_id"),
    )

    def __repr__(self) -> str:
        return f"<Contact(id={self.id}, name={self.name!r}, company_id={self.company_id})>"
