from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_roles
from app.db.session import get_session
from app.domain.enums import AuditSeverity
from app.repositories.audit import AuditEventRepository
from app.schemas.common import AuditEventRead

router = APIRouter()


@router.get("", response_model=dict)
async def list_events(
    type: str | None = None,
    severity: AuditSeverity | None = None,
    actor: int | None = None,
    session: AsyncSession = Depends(get_session),
    _user=Depends(require_roles("validator", "admin")),
):
    rows = await AuditEventRepository(session).list_filtered(type, severity, actor)
    return {"data": [AuditEventRead.model_validate(row) for row in rows]}
