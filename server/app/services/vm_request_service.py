from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.errors import ApiError
from app.domain.enums import AuditSeverity, NotificationType, RequestStatus, UserRole, VmStatus
from app.domain.models import User, VirtualMachine, VmRequest, VmTemplate
from app.repositories.vm_requests import VmRequestRepository
from app.schemas.common import VmRequestCreate, VmRequestPatch
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.services.provisioner import get_provisioner


class VmRequestService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.requests = VmRequestRepository(session)
        self.audit = AuditService(session)
        self.notifications = NotificationService(session)
        self.provisioner = get_provisioner()

    async def create(self, payload: VmRequestCreate, actor: User) -> VmRequest:
        if actor.role not in {UserRole.admin, UserRole.validator, UserRole.teacher} and actor.id != payload.requester_id:
            raise ApiError(403, "requester_mismatch", "Un étudiant ne peut créer une demande que pour son propre compte.")

        request = VmRequest(**payload.model_dump(), status=RequestStatus.pending)
        self.session.add(request)
        await self.session.flush()
        self.audit.record(
            "request_created",
            f"Demande #{request.id} créée.",
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
            await self._provision_request(request, actor)
        await self.session.commit()
        await self.session.refresh(request)
        return request

    async def approve_and_provision(self, request_id: int, actor: User) -> VmRequest:
        request = await self.requests.get(request_id)
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
            await self._provision_request(request, actor)
            await self.session.commit()
        except ApiError as exc:
            await self._mark_provisioning_failed(request_id, actor, exc.message)
            raise
        except Exception as exc:
            await self._mark_provisioning_failed(request_id, actor, str(exc) or exc.__class__.__name__)
            raise ApiError(500, "provisioning_failed", f"Provisionnement echoue: {str(exc) or exc.__class__.__name__}") from exc
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

    async def _provision_request(self, request: VmRequest, actor: User) -> None:
        owner = await self.session.get(User, request.requester_id)
        template = await self.session.get(VmTemplate, request.template_id)
        if not owner or not template:
            raise ApiError(422, "invalid_request_links", "Demande incomplete: utilisateur ou template introuvable.")

        provisioned_vms = await self.provisioner.create_vms(request, template, owner)
        for terraform_vm in provisioned_vms:
            vm = VirtualMachine(
                request_id=request.id,
                owner_id=owner.id,
                provider_vm_id=terraform_vm.provider_vm_id,
                name=terraform_vm.name,
                ip_address=terraform_vm.ip_address,
                status=VmStatus.running,
                ssh_username=terraform_vm.ssh_username,
                ssh_key_fingerprint=terraform_vm.ssh_key_fingerprint,
                network_segment=terraform_vm.network_segment,
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

        request.status = RequestStatus.provisioned
        await self.notifications.create_and_email(
            owner,
            NotificationType.vm_request_approved,
            "Demande VM approuvee",
            f"Votre demande #{request.id} a ete approuvee et provisionnee. Votre environnement est disponible dans Cloud Lab.",
            email_subject="Cloud Lab - demande VM approuvee",
        )

    async def _ensure_not_already_provisioned(self, request: VmRequest) -> None:
        existing_vm = await self.session.scalar(
            select(VirtualMachine).where(VirtualMachine.request_id == request.id)
        )
        if existing_vm:
            raise ApiError(
                409,
                "request_already_has_vm",
                f"La demande #{request.id} a deja une VM associee. Relance bloquee pour eviter les doublons.",
            )

    async def _mark_provisioning_failed(self, request_id: int, actor: User, message: str) -> None:
        try:
            await self.session.rollback()
        except Exception:
            pass
        try:
            from app.db.session import SessionLocal
            async with SessionLocal() as new_session:
                from app.repositories.vm_requests import VmRequestRepository
                from app.services.audit_service import AuditService
                repo = VmRequestRepository(new_session)
                request = await repo.get(request_id)
                if not request:
                    return
                request.status = RequestStatus.failed
                request.decision_comment = "Provisionnement echoue. Verification manuelle requise avant relance."
                short_message = (message or "Erreur inconnue").replace("\x00", "")[:900]
                AuditService(new_session).record(
                    "request_provisioning_failed",
                    f"Provisionnement echoue pour la demande #{request_id}: {short_message}",
                    severity=AuditSeverity.danger,
                    actor_id=actor.id if hasattr(actor, "id") else 0,
                    request_id=request_id,
                )
                await new_session.commit()
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("_mark_provisioning_failed error: %s", e)

    async def patch(self, request_id: int, payload: VmRequestPatch, actor: User) -> VmRequest:
        request = await self.requests.get(request_id)
        if not request:
            raise ApiError(404, "vm_request_not_found", "Demande VM introuvable.")
        if payload.validator_id and payload.validator_id != actor.id:
            raise ApiError(403, "validator_mismatch", "validator_id doit correspondre à l'utilisateur connecté.")

        request.status = payload.status
        request.validator_id = actor.id
        request.decision_comment = payload.decision_comment

        severity = AuditSeverity.success if payload.status == RequestStatus.approved else AuditSeverity.warning
        self.audit.record(
            f"request_{payload.status.value}",
            f"Demande #{request.id} mise à jour vers {payload.status.value}.",
            severity=severity,
            actor_id=actor.id,
            request_id=request.id,
        )
        if payload.status in {RequestStatus.approved, RequestStatus.refused}:
            is_approved = payload.status == RequestStatus.approved
            self.notifications.create(
                request.requester_id,
                NotificationType.vm_request_approved if is_approved else NotificationType.vm_request_refused,
                "Demande VM approuvée" if is_approved else "Demande VM refusée",
                f"Votre demande #{request.id} a été {'approuvée' if is_approved else 'refusée'}.",
            )
        await self.session.commit()
        await self.session.refresh(request)
        return request

    async def mark_provisioning_requested(self, request_id: int, actor: User) -> VmRequest:
        """Lance le provisionnement Terraform pour une demande approuvée ou en attente.

        FIX Bug 5 — idempotence :
        - Si la demande est déjà en provisioning/provisioned → retour silencieux.
        - Accepte pending ET approved (le validator peut provisionner directement).
        - Lève 409 uniquement pour les états terminaux (refused, failed, destroyed, expired).
        """
        request = await self.requests.get(request_id)
        if not request:
            raise ApiError(404, "vm_request_not_found", "Demande VM introuvable.")

        # Idempotence : déjà en cours ou terminé → OK
        if request.status in {RequestStatus.provisioning, RequestStatus.provisioned}:
            return request

        # États acceptés pour déclencher le provisionnement
        if request.status not in {RequestStatus.pending, RequestStatus.approved}:
            raise ApiError(
                409,
                "vm_request_not_provisionable",
                f"Impossible de provisionner une demande en statut '{request.status.value}'.",
            )

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
            await self._provision_request(request, actor)
            await self.session.commit()
        except ApiError as exc:
            await self._mark_provisioning_failed(request_id, actor, exc.message)
            raise
        except Exception as exc:
            await self._mark_provisioning_failed(request_id, actor, str(exc) or exc.__class__.__name__)
            raise ApiError(500, "provisioning_failed", f"Provisionnement echoue: {str(exc) or exc.__class__.__name__}") from exc
        await self.session.refresh(request)
        return request
