from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import AuditSeverity, NotificationType, VmStatus
from app.domain.models import VirtualMachine
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService


class VmLifecycleJob:
    """Tache data: detecte les VM arrivees en fin de vie sans toucher a l'infra."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit_service = AuditService(session)
        self.notification_service = NotificationService(session)

    async def mark_expired_vms(self, today: date | None = None) -> list[VirtualMachine]:
        current_date = today or date.today()
        result = await self.session.execute(
            select(VirtualMachine).where(
                VirtualMachine.end_date <= current_date,
                VirtualMachine.status.not_in([VmStatus.expired, VmStatus.destroyed]),
            )
        )
        vms = list(result.scalars().all())

        for vm in vms:
            vm.status = VmStatus.expired
            self.audit_service.record(
                "vm_expired",
                f"La VM {vm.name} a atteint sa date de fin et attend une destruction infra.",
                severity=AuditSeverity.warning,
                vm_id=vm.id,
            )
            self.notification_service.create(
                vm.owner_id,
                NotificationType.vm_expired,
                "VM arrivee en fin de vie",
                f"La VM {vm.name} est expiree. Elle doit etre detruite cote infrastructure.",
            )

        await self.session.flush()
        return vms
