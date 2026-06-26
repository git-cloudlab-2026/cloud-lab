import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.db.session import SessionLocal
from app.domain.enums import AuditSeverity, NotificationType, VmStatus
from app.domain.models import User, VirtualMachine, VmMetric, VmRequest, VmTemplate
from app.repositories.vms import VirtualMachineRepository, VmMetricRepository
from app.schemas.common import DestructionResult, ProvisioningResult, VirtualMachinePatch, VmMetricCreate
from app.services.ansible_service import AnsibleService
from app.services.audit_service import AuditService
from app.services.cost_service import CostService
from app.services.notification_service import NotificationService
from app.services.provisioner import get_provisioner


class VirtualMachineService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.vms = VirtualMachineRepository(session)
        self.metrics = VmMetricRepository(session)
        self.audit = AuditService(session)
        self.costs = CostService(session)
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
        await self.costs.refresh_vm(vm.id)
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

    async def retry_ansible(self, vm_id: int, actor: User) -> VirtualMachine:
        result = await self.session.execute(
            select(VirtualMachine, VmRequest, VmTemplate)
            .join(VmRequest, VmRequest.id == VirtualMachine.request_id)
            .join(VmTemplate, VmTemplate.id == VmRequest.template_id)
            .where(VirtualMachine.id == vm_id)
            .with_for_update()
        )
        row = result.one_or_none()
        if not row:
            raise ApiError(404, "vm_not_found", "VM introuvable.")
        vm, request, template = row
        if actor.role.value not in {"admin", "validator"}:
            raise ApiError(403, "vm_ansible_retry_forbidden", "Droits insuffisants pour relancer Ansible.")
        if vm.status in {VmStatus.destroyed, VmStatus.down}:
            raise ApiError(409, "vm_not_configurable", "Impossible de configurer une VM detruite ou en destruction.")
        if not vm.ip_address:
            raise ApiError(409, "vm_missing_ip", "Impossible de relancer Ansible: IP VM absente.")

        vm.status = VmStatus.configuring
        self.audit.record(
            "vm_ansible_retry_requested",
            f"Relance Ansible demandee pour {vm.name}.",
            severity=AuditSeverity.info,
            actor_id=actor.id,
            request_id=request.id,
            vm_id=vm.id,
        )
        await self.session.commit()
        await self.session.refresh(vm)
        asyncio.create_task(
            self._run_ansible_retry(
                vm_id=vm.id,
                request_id=request.id,
                actor_id=actor.id,
                vm_ip=vm.ip_address,
                vm_name=vm.name,
                template_type=template.ansible_playbook or template.name,
                course_name=template.name,
                end_date=vm.end_date.isoformat(),
                ssh_user=None,
            )
        )
        return vm

    async def destroy_with_provisioner(self, vm_id: int, actor: User) -> VirtualMachine:
        vm = await self._get_vm_for_update(vm_id)
        if not vm:
            raise ApiError(404, "vm_not_found", "VM introuvable.")
        if actor.role.value not in {"admin", "validator", "teacher"} and vm.owner_id != actor.id:
            raise ApiError(403, "vm_forbidden", "Vous ne pouvez consulter que vos propres VM.")
        if vm.status == VmStatus.destroyed:
            return vm
        if vm.status == VmStatus.down:
            raise ApiError(409, "vm_destroy_in_progress", "Destruction deja en cours pour cette VM.")
        if actor.role.value not in {"admin", "validator"} and vm.owner_id != actor.id:
            raise ApiError(403, "vm_destroy_forbidden", "Droits insuffisants pour detruire cette VM.")
        if not vm.provider_vm_id:
            raise ApiError(409, "vm_missing_provider_id", "Impossible de detruire: la VM n'a pas d'identifiant OpenStack.")

        vm.status = VmStatus.down
        await self.session.commit()
        try:
            await self.provisioner.destroy_vm(vm.provider_vm_id)
        except Exception:
            vm.status = VmStatus.error
            self.audit.record(
                "vm_destroy_failed",
                f"Destruction echouee pour VM {vm.name}.",
                severity=AuditSeverity.danger,
                actor_id=actor.id,
                vm_id=vm.id,
            )
            await self.session.commit()
            raise
        vm.status = VmStatus.destroyed
        vm.destroyed_at = datetime.now(timezone.utc)
        await self.costs.refresh_vm(vm.id)
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

    async def destroy_with_mock(self, vm_id: int, actor: User) -> VirtualMachine:
        return await self.destroy_with_provisioner(vm_id, actor)

    async def _get_vm_for_update(self, vm_id: int) -> VirtualMachine | None:
        return await self.session.scalar(
            select(VirtualMachine).where(VirtualMachine.id == vm_id).with_for_update()
        )

    @staticmethod
    async def _run_ansible_retry(
        *,
        vm_id: int,
        request_id: int,
        actor_id: int,
        vm_ip: str,
        vm_name: str,
        template_type: str,
        course_name: str,
        end_date: str,
        ssh_user: str | None,
    ) -> None:
        async with SessionLocal() as session:
            audit = AuditService(session)
            ansible = AnsibleService()
            vm = await session.get(VirtualMachine, vm_id)
            if not vm:
                return
            target_ip = AnsibleService.select_target_ip(vm_ip)
            audit.record(
                "vm_ansible_started",
                f"Configuration Ansible relancee pour {vm_name} via {target_ip}.",
                severity=AuditSeverity.info,
                actor_id=actor_id,
                request_id=request_id,
                vm_id=vm_id,
            )
            await session.commit()
            try:
                result = await ansible.run_playbook(
                    vm_ip=vm_ip,
                    template_type=template_type,
                    vm_name=vm_name,
                    course_name=course_name,
                    end_date=end_date,
                    request_id=request_id,
                    ssh_user=ssh_user,
                )
            except ApiError as exc:
                vm.status = VmStatus.error
                audit.record(
                    "vm_ansible_failed",
                    f"Configuration Ansible echouee pour {vm_name}: {VirtualMachineService._short_log(exc.message)}",
                    severity=AuditSeverity.danger,
                    actor_id=actor_id,
                    request_id=request_id,
                    vm_id=vm_id,
                )
                await session.commit()
                return
            except Exception as exc:
                vm.status = VmStatus.error
                audit.record(
                    "vm_ansible_failed",
                    f"Configuration Ansible interrompue pour {vm_name}: {VirtualMachineService._short_log(str(exc) or exc.__class__.__name__)}",
                    severity=AuditSeverity.danger,
                    actor_id=actor_id,
                    request_id=request_id,
                    vm_id=vm_id,
                )
                await session.commit()
                return

            vm.status = VmStatus.running
            event_type = "vm_ansible_skipped" if result.skipped else "vm_ansible_completed"
            audit.record(
                event_type,
                f"Configuration Ansible terminee pour {vm_name}. {VirtualMachineService._ansible_summary(result.stdout)}",
                severity=AuditSeverity.success if not result.skipped else AuditSeverity.info,
                actor_id=actor_id,
                request_id=request_id,
                vm_id=vm_id,
            )
            await session.commit()

    @staticmethod
    def _short_log(message: str, limit: int = 900) -> str:
        clean = (message or "").replace("\x00", "").strip()
        return clean[-limit:] if len(clean) > limit else clean

    @staticmethod
    def _ansible_summary(stdout: str) -> str:
        clean = (stdout or "").replace("\x00", "").strip()
        if "PLAY RECAP" in clean:
            return "PLAY RECAP" + VirtualMachineService._short_log(clean.split("PLAY RECAP", 1)[1], limit=500)
        return VirtualMachineService._short_log(clean, limit=500)
