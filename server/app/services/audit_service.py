from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import AuditSeverity
from app.domain.models import AuditEvent


class AuditService:
    def __init__(self, session: AsyncSession):
        self.session = session

    def record(
        self,
        event_type: str,
        message: str,
        *,
        severity: AuditSeverity = AuditSeverity.info,
        actor_id: int | None = None,
        request_id: int | None = None,
        vm_id: int | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            actor_id=actor_id,
            request_id=request_id,
            vm_id=vm_id,
            event_type=event_type,
            severity=severity,
            event_message=message,
        )
        self.session.add(event)
        return event
