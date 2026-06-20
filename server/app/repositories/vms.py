from sqlalchemy import select

from app.domain.enums import VmStatus
from app.domain.models import CostRecord, VirtualMachine, VmMetric
from app.repositories.base import Repository


class VirtualMachineRepository(Repository[VirtualMachine]):
    model = VirtualMachine

    async def list_filtered(self, status: VmStatus | None = None, owner_id: int | None = None) -> list[VirtualMachine]:
        stmt = select(VirtualMachine).order_by(VirtualMachine.created_at.desc())
        if status:
            stmt = stmt.where(VirtualMachine.status == status)
        if owner_id:
            stmt = stmt.where(VirtualMachine.owner_id == owner_id)
        result = await self.session.execute(stmt)
        return list(result.scalars())


class VmMetricRepository(Repository[VmMetric]):
    model = VmMetric

    async def list_global(self, limit: int = 100) -> list[VmMetric]:
        result = await self.session.execute(select(VmMetric).order_by(VmMetric.collected_at.desc()).limit(limit))
        return list(result.scalars())

    async def history_for_vm(self, vm_id: int, limit: int = 50) -> list[VmMetric]:
        result = await self.session.execute(
            select(VmMetric).where(VmMetric.vm_id == vm_id).order_by(VmMetric.collected_at.desc()).limit(limit)
        )
        return list(result.scalars())


class CostRecordRepository(Repository[CostRecord]):
    model = CostRecord
