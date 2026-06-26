import asyncio
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.db.session import SessionLocal
from app.domain.enums import AuditSeverity, NotificationType, RequestStatus, UserRole, VmStatus
from app.domain.models import User, VirtualMachine, VmRequest, VmTemplate
from app.repositories.vm_requests import VmRequestRepository
from app.services.ansible_service import AnsibleService
from app.schemas.common import VmRequestCreate, VmRequestPatch
from app.services.audit_service import AuditService
from app.services.cost_service import CostService
from app.services.notification_service import NotificationService
from app.services.provisioner import get_provisioner


@dataclass(frozen=True)
class AnsibleProvisioningJob:
    vm_id: int
    request_id: int
    actor_id: int
    vm_ip: str | None
    vm_name: str
    template_type: str
    course_name: str
    end_date: str
    ssh_user: str | None


class VmRequestService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.requests = VmRequestRepository(session)
        self.audit = AuditService(session)
        self.costs = CostService(session)
        self.notifications = NotificationService(session)
        self.provisioner = get_provisioner()
        self.ansible = AnsibleService()

    async def create(self, payload: VmRequestCreate, actor: User) -> VmRequest:
        if actor.role not in {UserRole.admin, UserRole.validator, UserRole.teacher} and actor.id != payload.requester_id:
            raise ApiError(403, "requester_mismatch", "Un etudiant ne peut creer une demande que pour son propre compte.")

        request = VmRequest(**payload.model_dump(), status=RequestStatus.pending)
        self.session.add(request)
        await self.session.flush()
        self.audit.record(
            "request_created",
            f"Demande #{request.id} creee.",
            severity=AuditSeverity.success,
            actor_id=actor.id,
            request_id=request.id,
        )
        if actor.role == UserRole.teacher:
            request.status = RequestStatus.provisioning
            request.validator_id = actor.id
            request.decision_comment = "Demande formateur auto-validee pour un cours."
            self.audit.record(
                "teacher_request_auto_approved",
                f"Demande formateur #{request.id} auto-validee.",
                severity=AuditSeverity.success,
                actor_id=actor.id,
                request_id=request.id,
            )
            await self.session.commit()
            try:
                ansible_jobs = await self._provision_request(request, actor)
                await self.session.commit()
                self._schedule_ansible_jobs(ansible_jobs)
            except ApiError as exc:
                await self._mark_provisioning_failed(request.id, actor, exc.message)
                raise
            except Exception as exc:
                message = str(exc) or exc.__class__.__name__
                await self._mark_provisioning_failed(request.id, actor, message)
                raise ApiError(500, "provisioning_failed", f"Provisionnement echoue: {message}") from exc
        else:
            await self.session.commit()
        await self.session.refresh(request)
        return request

    async def approve_and_provision(self, request_id: int, actor: User) -> VmRequest:
        request = await self._get_request_for_update(request_id)
        if not request:
            raise ApiError(404, "vm_request_not_found", "Demande VM introuvable.")
        if request.status not in {RequestStatus.pending, RequestStatus.approved}:
            raise ApiError(409, "invalid_request_status", "Seule une demande en attente ou approuvee peut etre provisionnee.")

        await self._ensure_not_already_provisioned(request)
        request.status = RequestStatus.provisioning
        request.validator_id = actor.id
        request.decision_comment = "Demande approuvee et provisionnement lance."
        self.audit.record(
            "request_approved",
            f"Demande #{request.id} approuvee par {actor.full_name}.",
            severity=AuditSeverity.success,
            actor_id=actor.id,
            request_id=request.id,
        )
        await self.session.commit()
        try:
            ansible_jobs = await self._provision_request(request, actor)
            await self.session.commit()
            self._schedule_ansible_jobs(ansible_jobs)
        except ApiError as exc:
            await self._mark_provisioning_failed(request_id, actor, exc.message)
            raise
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            await self._mark_provisioning_failed(request_id, actor, message)
            raise ApiError(500, "provisioning_failed", f"Provisionnement echoue: {message}") from exc
        await self.session.refresh(request)
        return request

    async def reject(self, request_id: int, reason: str, actor: User) -> VmRequest:
        request = await self.requests.get(request_id)
        if not request:
            raise ApiError(404, "vm_request_not_found", "Demande VM introuvable.")
        if request.status != RequestStatus.pending:
            raise ApiError(409, "invalid_request_status", "Seule une demande en attente peut etre refusee.")

        request.status = RequestStatus.refused
        request.validator_id = actor.id
        request.decision_comment = reason
        self.audit.record(
            "request_refused",
            f"Demande #{request.id} refusee: {reason}",
            severity=AuditSeverity.warning,
            actor_id=actor.id,
            request_id=request.id,
        )
        self.notifications.create(
            request.requester_id,
            NotificationType.vm_request_refused,
            "Demande VM refusee",
            f"Votre demande #{request.id} a ete refusee: {reason}",
        )
        await self.session.commit()
        await self.session.refresh(request)
        return request

    async def _provision_request(self, request: VmRequest, actor: User) -> list[AnsibleProvisioningJob]:
        owner = await self.session.get(User, request.requester_id)
        template = await self.session.get(VmTemplate, request.template_id)
        if not owner or not template:
            raise ApiError(422, "invalid_request_links", "Demande incomplete: utilisateur ou template introuvable.")

        provisioned_vms = await self.provisioner.create_vms(request, template, owner)
        ansible_jobs: list[AnsibleProvisioningJob] = []
        for provisioned_vm in provisioned_vms:
            vm = VirtualMachine(
                request_id=request.id,
                owner_id=owner.id,
                provider_vm_id=provisioned_vm.provider_vm_id,
                name=provisioned_vm.name,
                ip_address=provisioned_vm.ip_address,
                status=VmStatus.configuring if self.ansible.settings.ansible_enabled else VmStatus.running,
                ssh_username=provisioned_vm.ssh_username,
                ssh_key_fingerprint=provisioned_vm.ssh_key_fingerprint,
                network_segment=provisioned_vm.network_segment,
                start_date=request.start_date,
                end_date=request.end_date,
            )
            self.session.add(vm)
            await self.session.flush()
            self.audit.record(
                "vm_created",
                f"VM {vm.name} creee pour la demande #{request.id}.",
                severity=AuditSeverity.success,
                actor_id=actor.id,
                request_id=request.id,
                vm_id=vm.id,
            )
            await self.costs.refresh_vm(vm.id)
            ansible_jobs.append(
                AnsibleProvisioningJob(
                    vm_id=vm.id,
                    request_id=request.id,
                    actor_id=actor.id,
                    vm_ip=vm.ip_address,
                    vm_name=vm.name,
                    template_type=template.ansible_playbook or template.name,
                    course_name=template.name,
                    end_date=request.end_date.isoformat(),
                    ssh_user=None,
                )
            )

        request.status = RequestStatus.provisioned
        self.notifications.create(
            request.requester_id,
            NotificationType.vm_request_approved,
            "Demande VM approuvee",
            f"Votre demande #{request.id} a ete approuvee et provisionnee. Votre environnement est disponible dans Cloud Lab.",
        )
        return ansible_jobs

    async def _ensure_not_already_provisioned(self, request: VmRequest) -> None:
        existing_vm = await self.session.scalar(select(VirtualMachine).where(VirtualMachine.request_id == request.id))
        if existing_vm:
            raise ApiError(
                409,
                "request_already_has_vm",
                f"La demande #{request.id} a deja une VM associee. Relance bloquee pour eviter les doublons.",
            )

    async def _mark_provisioning_failed(self, request_id: int, actor: User, message: str) -> None:
        await self.session.rollback()
        request = await self.requests.get(request_id)
        if not request:
            return
        request.status = RequestStatus.failed
        request.decision_comment = "Provisionnement echoue. Verification manuelle requise avant relance."
        short_message = (message or "Erreur inconnue").replace("\x00", "")[:900]
        self.audit.record(
            "request_provisioning_failed",
            f"Provisionnement echoue pour la demande #{request_id}: {short_message}",
            severity=AuditSeverity.danger,
            actor_id=actor.id,
            request_id=request_id,
        )
        await self.session.commit()

    async def patch(self, request_id: int, payload: VmRequestPatch, actor: User) -> VmRequest:
        request = await self.requests.get(request_id)
        if not request:
            raise ApiError(404, "vm_request_not_found", "Demande VM introuvable.")
        if payload.validator_id and payload.validator_id != actor.id:
            raise ApiError(403, "validator_mismatch", "validator_id doit correspondre a l'utilisateur connecte.")

        request.status = payload.status
        request.validator_id = actor.id
        request.decision_comment = payload.decision_comment

        severity = AuditSeverity.success if payload.status == RequestStatus.approved else AuditSeverity.warning
        self.audit.record(
            f"request_{payload.status.value}",
            f"Demande #{request.id} mise a jour vers {payload.status.value}.",
            severity=severity,
            actor_id=actor.id,
            request_id=request.id,
        )
        if payload.status in {RequestStatus.approved, RequestStatus.refused}:
            is_approved = payload.status == RequestStatus.approved
            self.notifications.create(
                request.requester_id,
                NotificationType.vm_request_approved if is_approved else NotificationType.vm_request_refused,
                "Demande VM approuvee" if is_approved else "Demande VM refusee",
                f"Votre demande #{request.id} a ete {'approuvee' if is_approved else 'refusee'}.",
            )
        await self.session.commit()
        await self.session.refresh(request)
        return request

    @staticmethod
    def _short_log(message: str, limit: int = 900) -> str:
        clean = (message or "").replace("\x00", "").strip()
        if len(clean) <= limit:
            return clean
        return clean[-limit:]

    async def mark_provisioning_requested(self, request_id: int, actor: User) -> VmRequest:
        request = await self._get_request_for_update(request_id)
        if not request:
            raise ApiError(404, "vm_request_not_found", "Demande VM introuvable.")
        if request.status != RequestStatus.approved:
            raise ApiError(409, "vm_request_not_approved", "Seule une demande approuvee peut passer en provisionnement.")

        await self._ensure_not_already_provisioned(request)
        request.status = RequestStatus.provisioning
        self.audit.record(
            "provisioning_requested",
            f"Provisionnement demande pour la demande #{request_id}.",
            actor_id=actor.id,
            request_id=request_id,
        )
        await self.session.commit()
        try:
            ansible_jobs = await self._provision_request(request, actor)
            await self.session.commit()
            self._schedule_ansible_jobs(ansible_jobs)
        except ApiError as exc:
            await self._mark_provisioning_failed(request_id, actor, exc.message)
            raise
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            await self._mark_provisioning_failed(request_id, actor, message)
            raise ApiError(500, "provisioning_failed", f"Provisionnement echoue: {message}") from exc
        await self.session.refresh(request)
        return request

    async def _get_request_for_update(self, request_id: int) -> VmRequest | None:
        return await self.session.scalar(
            select(VmRequest).where(VmRequest.id == request_id).with_for_update()
        )

    def _schedule_ansible_jobs(self, jobs: list[AnsibleProvisioningJob]) -> None:
        for job in jobs:
            asyncio.create_task(self._run_ansible_job(job))

    @staticmethod
    async def _run_ansible_job(job: AnsibleProvisioningJob) -> None:
        async with SessionLocal() as session:
            audit = AuditService(session)
            ansible = AnsibleService()
            vm = await session.get(VirtualMachine, job.vm_id)
            if not vm:
                return
            vm.status = VmStatus.configuring
            target_ip = AnsibleService.select_target_ip(job.vm_ip or "")
            audit.record(
                "vm_ansible_started",
                f"Configuration Ansible lancee pour {job.vm_name} via {target_ip}.",
                severity=AuditSeverity.info,
                actor_id=job.actor_id,
                request_id=job.request_id,
                vm_id=job.vm_id,
            )
            await session.commit()
            try:
                result = await ansible.run_playbook(
                    vm_ip=job.vm_ip,
                    template_type=job.template_type,
                    vm_name=job.vm_name,
                    course_name=job.course_name,
                    end_date=job.end_date,
                    request_id=job.request_id,
                    ssh_user=job.ssh_user,
                )
            except ApiError as exc:
                vm.status = VmStatus.error
                audit.record(
                    "vm_ansible_failed",
                    f"Configuration Ansible echouee pour {job.vm_name}: {VmRequestService._short_log(exc.message)}",
                    severity=AuditSeverity.danger,
                    actor_id=job.actor_id,
                    request_id=job.request_id,
                    vm_id=job.vm_id,
                )
                await session.commit()
                return
            except Exception as exc:
                vm.status = VmStatus.error
                message = str(exc) or exc.__class__.__name__
                audit.record(
                    "vm_ansible_failed",
                    f"Configuration Ansible interrompue pour {job.vm_name}: {VmRequestService._short_log(message)}",
                    severity=AuditSeverity.danger,
                    actor_id=job.actor_id,
                    request_id=job.request_id,
                    vm_id=job.vm_id,
                )
                await session.commit()
                return
            if result.skipped:
                vm.status = VmStatus.running
                audit.record(
                    "vm_ansible_skipped",
                    f"Configuration Ansible ignoree pour {job.vm_name}: {VmRequestService._short_log(result.stdout)}",
                    severity=AuditSeverity.info,
                    actor_id=job.actor_id,
                    request_id=job.request_id,
                    vm_id=job.vm_id,
                )
            else:
                vm.status = VmStatus.running
                audit.record(
                    "vm_ansible_completed",
                    f"Configuration Ansible terminee pour {job.vm_name}. {VmRequestService._ansible_summary(result.stdout)}",
                    severity=AuditSeverity.success,
                    actor_id=job.actor_id,
                    request_id=job.request_id,
                    vm_id=job.vm_id,
                )
            await session.commit()

    @staticmethod
    def _ansible_summary(stdout: str) -> str:
        clean = (stdout or "").replace("\x00", "").strip()
        if "PLAY RECAP" in clean:
            recap = clean.split("PLAY RECAP", 1)[1]
            return "PLAY RECAP" + VmRequestService._short_log(recap, limit=500)
        return VmRequestService._short_log(clean, limit=500)
