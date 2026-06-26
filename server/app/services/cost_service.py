from datetime import datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import VmStatus
from app.domain.models import CostRecord, VirtualMachine, VmRequest, VmTemplate


SWISS_TZ = ZoneInfo("Europe/Zurich")
MONEY = Decimal("0.01")
HOURS = Decimal("0.01")


class CostService:
    """Internal cost model until a provider billing API is available.

    Cost is computed from the VM runtime and the hourly CHF price stored on the
    VM template. It is not an Infomaniak invoice; it is the product's reliable
    operational estimate.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def refresh_all(self) -> None:
        result = await self.session.execute(select(VirtualMachine.id))
        for vm_id in result.scalars():
            await self.refresh_vm(vm_id)

    async def refresh_vm(self, vm_id: int) -> None:
        result = await self.session.execute(
            select(VirtualMachine, VmTemplate)
            .join(VmRequest, VmRequest.id == VirtualMachine.request_id)
            .join(VmTemplate, VmTemplate.id == VmRequest.template_id)
            .where(VirtualMachine.id == vm_id)
        )
        row = result.one_or_none()
        if not row:
            return

        vm, template = row
        await self.session.execute(delete(CostRecord).where(CostRecord.vm_id == vm.id))

        started_at = self._as_swiss_time(vm.created_at)
        ended_at = self._billing_end(vm)
        if not started_at or not ended_at or ended_at <= started_at:
            return

        hourly_cost = Decimal(template.estimated_cost_per_hour_chf or 0)
        if hourly_cost <= 0:
            return

        for cost_date, hours_running in self._daily_hours(started_at, ended_at):
            cost = (hours_running * hourly_cost).quantize(MONEY, rounding=ROUND_HALF_UP)
            self.session.add(
                CostRecord(
                    vm_id=vm.id,
                    cost_date=cost_date,
                    hours_running=hours_running.quantize(HOURS, rounding=ROUND_HALF_UP),
                    cost_estimate_chf=cost,
                )
            )

    @staticmethod
    def _as_swiss_time(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(SWISS_TZ)

    def _billing_end(self, vm: VirtualMachine) -> datetime:
        if vm.destroyed_at:
            return self._as_swiss_time(vm.destroyed_at) or datetime.now(SWISS_TZ)
        if vm.status in {VmStatus.destroyed, VmStatus.error}:
            return self._as_swiss_time(vm.created_at) or datetime.now(SWISS_TZ)
        return datetime.now(SWISS_TZ)

    @staticmethod
    def _daily_hours(started_at: datetime, ended_at: datetime) -> list[tuple[datetime.date, Decimal]]:
        rows: list[tuple[datetime.date, Decimal]] = []
        cursor = started_at
        while cursor < ended_at:
            next_midnight = datetime.combine(cursor.date() + timedelta(days=1), time.min, tzinfo=SWISS_TZ)
            slice_end = min(next_midnight, ended_at)
            hours = Decimal(str((slice_end - cursor).total_seconds() / 3600))
            if hours > 0:
                rows.append((cursor.date(), hours))
            cursor = slice_end
        return rows
