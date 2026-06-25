from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import AuditSeverity, NotificationType, VmStatus
from app.domain.models import Notification, User, VirtualMachine
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.services.provisioner import get_provisioner


class VmLifecycleJob:
    """Tache de cycle de vie: alertes 24h et destruction des VM arrivees a date de fin."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit_service = AuditService(session)
        self.notification_service = NotificationService(session)
        self.provisioner = get_provisioner()

    async def mark_expired_vms(self, today: date | None = None) -> list[VirtualMachine]:
        current_date = today or datetime.now(ZoneInfo("Europe/Zurich")).date()
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

    async def destroy_due_vms(self, today: date | None = None) -> list[VirtualMachine]:
        """Detruit reellement les VM dont la date de fin est atteinte.

        La destruction passe par le provisioner actif, donc le comportement est le
        meme que le bouton "Detruire" du portail.
        """
        current_date = today or datetime.now(ZoneInfo("Europe/Zurich")).date()
        result = await self.session.execute(
            select(VirtualMachine).where(
                VirtualMachine.end_date <= current_date,
                VirtualMachine.status.in_([VmStatus.running, VmStatus.stopped, VmStatus.expired]),
            )
        )
        vms = list(result.scalars().all())
        destroyed: list[VirtualMachine] = []

        for vm in vms:
            if not vm.provider_vm_id:
                vm.status = VmStatus.error
                self.audit_service.record(
                    "vm_auto_destroy_failed",
                    f"Destruction automatique impossible pour {vm.name}: provider_vm_id manquant.",
                    severity=AuditSeverity.danger,
                    vm_id=vm.id,
                )
                await self.session.commit()
                continue

            vm.status = VmStatus.down
            self.audit_service.record(
                "vm_auto_destroy_started",
                f"Destruction automatique lancee pour {vm.name} arrivee a date de fin.",
                severity=AuditSeverity.warning,
                vm_id=vm.id,
            )
            await self.session.commit()

            try:
                await self.provisioner.destroy_vm(vm.provider_vm_id)
            except Exception as exc:
                vm.status = VmStatus.error
                self.audit_service.record(
                    "vm_auto_destroy_failed",
                    f"Destruction automatique echouee pour {vm.name}: {str(exc)[:500]}",
                    severity=AuditSeverity.danger,
                    vm_id=vm.id,
                )
                await self.session.commit()
                continue

            vm.status = VmStatus.destroyed
            vm.destroyed_at = datetime.now(timezone.utc)
            self.audit_service.record(
                "vm_auto_destroyed",
                f"VM {vm.name} detruite automatiquement a sa date de fin.",
                severity=AuditSeverity.danger,
                vm_id=vm.id,
            )
            self.notification_service.create(
                vm.owner_id,
                NotificationType.vm_destroyed,
                "VM detruite automatiquement",
                f"La VM {vm.name} a ete detruite automatiquement a sa date de fin.",
            )
            await self.session.commit()
            destroyed.append(vm)

        return destroyed

    async def notify_expiring_soon_vms(self, today: date | None = None) -> list[VirtualMachine]:
        current_date = today or datetime.now(ZoneInfo("Europe/Zurich")).date()
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
        destroyed = await self.destroy_due_vms(today)
        return {"expiring_soon": len(expiring_soon), "destroyed": len(destroyed)}
