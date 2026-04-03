from datetime import datetime

from pydantic import BaseModel

from app.models.enums import AuditLogStatus, AuditLogTarget, SignalAction


class AuditLogResponse(BaseModel):
    id: int
    signal_id: int
    action_type: SignalAction
    target: AuditLogTarget
    target_id: str | None
    status: AuditLogStatus
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogWithSignalResponse(AuditLogResponse):
    company_name: str | None = None
    company_domain: str | None = None
