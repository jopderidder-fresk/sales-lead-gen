from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import AuditLogStatus, AuditLogTarget, SignalAction


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    signal_id: Mapped[int] = mapped_column(ForeignKey("signals.id", ondelete="CASCADE"))
    action_type: Mapped[SignalAction] = mapped_column(
        Enum(SignalAction, values_callable=lambda e: [x.value for x in e])
    )
    target: Mapped[AuditLogTarget] = mapped_column(
        Enum(AuditLogTarget, values_callable=lambda e: [x.value for x in e])
    )
    target_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[AuditLogStatus] = mapped_column(
        Enum(AuditLogStatus, values_callable=lambda e: [x.value for x in e])
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    signal: Mapped["Signal"] = relationship(back_populates="audit_logs")  # noqa: F821

    __table_args__ = (
        Index("ix_audit_logs_signal_id", "signal_id"),
        Index("ix_audit_logs_action_type", "action_type"),
        Index("ix_audit_logs_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog(id={self.id}, signal_id={self.signal_id}, "
            f"action={self.action_type!r}, target={self.target!r}, status={self.status!r})>"
        )
