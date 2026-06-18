from sqlalchemy import select

from app.domain.enums import AuditSeverity
from app.domain.models import AuditEvent
from app.repositories.base import Repository


class AuditEventRepository(Repository[AuditEvent]):
    model = AuditEvent

    async def list_filtered(
        self,
        event_type: str | None = None,
        severity: AuditSeverity | None = None,
        actor_id: int | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        stmt = select(AuditEvent)
        if event_type:
            stmt = stmt.where(AuditEvent.event_type == event_type)
        if severity:
            stmt = stmt.where(AuditEvent.severity == severity)
        if actor_id:
            stmt = stmt.where(AuditEvent.actor_id == actor_id)
        stmt = stmt.order_by(AuditEvent.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars())
