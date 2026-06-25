from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.domain.enums import AuditSeverity, NotificationType, VmStatus
from app.domain.models import User, VirtualMachine, VmMetric
from app.repositories.vms import VirtualMachineRepository, VmMetricRepository
from app.schemas.common import DestructionResult, ProvisioningResult, VirtualMachinePatch, VmMetricCreate
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.services.provisioner import get_provisioner


class VirtualMachineService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.vms = VirtualMachineRepository(session)
        self.metrics = VmMetricRepository(session)
        self.audit = AuditService(session)
        self.notifications = NotificationService(session)
        self.provisioner = get_provisioner()

    async def get_visible_vm(self, vm_id: int, actor: User) -> VirtualMachine:
        vm = await self.vms.get(vm_id)
        if not vm:
            raise ApiError(404, "vm_not_found", "VM introuvable.")
        if actor.role.value not in {"admin", "validator", "teacher"} and vm.owner_id != actor.id:
            raise ApiError(403, "vm_forbidden", "Vous ne pouvez consulter que vos propres VM.")
        return vm

    async def patch_status(self, vm_id: int, payload: VirtualMachinePatch, actor: User) -> VirtualMachine:
        vm = await self.vms.get(vm_id)
        if not vm:
            raise ApiError(404, "vm_not_found", "VM introuvable.")
        vm.status = payload.status
        self.audit.record("vm_status_changed", f"VM #{vm.id} passée à {payload.status.value}.", actor_id=actor.id, vm_id=vm.id)
        await self.session.commit()
        await self.session.refresh(vm)
        return vm

    async def provisioning_result(self, vm_id: int, payload: ProvisioningResult, actor: User) -> VirtualMachine:
        vm = await self.vms.get(vm_id)
        if not vm:
            raise ApiError(404, "vm_not_found", "VM introuvable.")
        vm.provider_vm_id = payload.provider_vm_id
        vm.ip_address = payload.ip_address
        vm.network_segment = payload.network_segment
        vm.status = payload.status
        event_type = "vm_provisioned" if payload.status == VmStatus.running else "vm_provisioning_failed"
        severity = AuditSeverity.success if payload.status == VmStatus.running else AuditSeverity.danger
        self.audit.record(event_type, f"Résultat de provisionnement reçu pour VM #{vm.id}.", severity=severity, actor_id=actor.id, vm_id=vm.id)
        await self.session.commit()
        await self.session.refresh(vm)
        return vm

    async def destruction_result(self, vm_id: int, payload: DestructionResult, actor: User) -> VirtualMachine:
        vm = await self.vms.get(vm_id)
        if not vm:
            raise ApiError(404, "vm_not_found", "VM introuvable.")
        if payload.status != VmStatus.destroyed:
            raise ApiError(422, "invalid_destruction_status", "La destruction doit retourner status=destroyed.")
        vm.status = VmStatus.destroyed
        vm.destroyed_at = payload.destroyed_at or datetime.now(timezone.utc)
        self.audit.record("vm_destroyed", f"VM #{vm.id} marquée détruite.", severity=AuditSeverity.danger, actor_id=actor.id, vm_id=vm.id)
        self.notifications.create(vm.owner_id, NotificationType.vm_destroyed, "VM détruite", f"La VM {vm.name} a été détruite.")
        await self.session.commit()
        await self.session.refresh(vm)
        return vm

    async def add_metric(self, vm_id: int, payload: VmMetricCreate) -> VmMetric:
        vm = await self.vms.get(vm_id)
        if not vm:
            raise ApiError(404, "vm_not_found", "VM introuvable.")
        metric = VmMetric(vm_id=vm_id, **payload.model_dump())
        self.session.add(metric)
        await self.session.commit()
        await self.session.refresh(metric)
        return metric

    async def destroy(self, vm_id: int, actor: User) -> VirtualMachine:
        vm = await self.get_visible_vm(vm_id, actor)
        if vm.status == VmStatus.destroyed:
            return vm
        if actor.role.value not in {"admin", "validator"} and vm.owner_id != actor.id:
            raise ApiError(403, "vm_destroy_forbidden", "Droits insuffisants pour detruire cette VM.")

        await self.provisioner.destroy_vm(vm.provider_vm_id)
        vm.status = VmStatus.destroyed
        vm.destroyed_at = datetime.now(timezone.utc)
        self.audit.record(
            "vm_destroyed_by_provisioner",
            f"VM {vm.name} detruite par le provisioner.",
            severity=AuditSeverity.danger,
            actor_id=actor.id,
            vm_id=vm.id,
        )
        self.notifications.create(
            vm.owner_id,
            NotificationType.vm_destroyed,
            "VM detruite",
            f"La VM {vm.name} a ete detruite.",
        )
        await self.session.commit()
        await self.session.refresh(vm)
        return vm