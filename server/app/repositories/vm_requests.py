from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.domain.enums import RequestStatus
from app.domain.models import VmRequest
from app.repositories.base import Repository


class VmRequestRepository(Repository[VmRequest]):
    model = VmRequest

    async def list_filtered(self, status: RequestStatus | None = None) -> list[VmRequest]:
        stmt = (
            select(VmRequest)
            .options(selectinload(VmRequest.requester), selectinload(VmRequest.course), selectinload(VmRequest.template))
            .order_by(VmRequest.created_at.desc(), VmRequest.id.desc())
        )
        if status:
            stmt = stmt.where(VmRequest.status == status)
        result = await self.session.execute(stmt)
        return list(result.scalars())
