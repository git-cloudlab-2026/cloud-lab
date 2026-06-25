from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import AuditSeverity, NotificationType, VmStatus
from app.domain.models import Notification, User, VirtualMachine
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

    async def notify_expiring_soon_vms(self, today: date | None = None) -> list[VirtualMachine]:
        current_date = today or date.today()
        target_date = current_date + timedelta(days=1)
        result = await self.session.execute(
            select(VirtualMachine).where(
                VirtualMachine.end_date == target_date,
                VirtualMachine.status.in_([VmStatus.running, VmStatus.stopped, VmStatus.down]),
            )
        )
        vms = list(result.scalars().all())
        notified: list[VirtualMachine] = []

        for vm in vms:
            already_notified = await self.session.scalar(
                select(Notification).where(
                    Notification.user_id == vm.owner_id,
                    Notification.type == NotificationType.vm_expiring_soon,
                    Notification.message.contains(vm.name),
                )
            )
            if already_notified:
                continue

            owner = await self.session.get(User, vm.owner_id)
            if not owner:
                continue

            message = (
                f"La VM {vm.name} expire le {vm.end_date}. "
                "Sauvegardez vos travaux et demandez une prolongation si necessaire."
            )
            await self.notification_service.create_and_email(
                owner,
                NotificationType.vm_expiring_soon,
                "VM bientot expiree",
                message,
                email_subject="Cloud Lab - VM expire dans 24h",
            )
            self.audit_service.record(
                "vm_expiring_soon",
                f"Alerte 24h envoyee pour la VM {vm.name}.",
                severity=AuditSeverity.warning,
                vm_id=vm.id,
            )
            notified.append(vm)

        await self.session.flush()
        return notified

    async def run(self, today: date | None = None) -> dict[str, int]:
        expiring_soon = await self.notify_expiring_soon_vms(today)
        expired = await self.mark_expired_vms(today)
        return {"expiring_soon": len(expiring_soon), "expired": len(expired)}
