from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import SignalAction, SignalType


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    source_url: Mapped[str | None] = mapped_column(String(2048))
    source_title: Mapped[str | None] = mapped_column(String(512))
    signal_type: Mapped[SignalType] = mapped_column(Enum(SignalType, values_callable=lambda e: [x.value for x in e]))
    relevance_score: Mapped[float | None] = mapped_column()
    llm_summary: Mapped[str | None] = mapped_column(Text)
    raw_content_hash: Mapped[str | None] = mapped_column(String(64))
    action_taken: Mapped[SignalAction | None] = mapped_column(Enum(SignalAction, values_callable=lambda e: [x.value for x in e]))
    raw_markdown: Mapped[str | None] = mapped_column(Text)
    is_processed: Mapped[bool] = mapped_column(default=False, server_default="false")
    action_executed_at: Mapped[datetime | None] = mapped_column()
    crm_commented_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="signals")  # noqa: F821
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="signal")  # noqa: F821

    __table_args__ = (
        Index("ix_signals_company_id", "company_id"),
        Index("ix_signals_created_at", "created_at"),
        Index("ix_signals_signal_type", "signal_type"),
        Index("ix_signals_is_processed", "is_processed"),
    )

    def __repr__(self) -> str:
        return f"<Signal(id={self.id}, type={self.signal_type!r}, company_id={self.company_id})>"
