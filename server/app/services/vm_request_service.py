from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.domain.enums import AuditSeverity, NotificationType, RequestStatus, UserRole
from app.domain.models import User, VmRequest
from app.repositories.vm_requests import VmRequestRepository
from app.schemas.common import VmRequestCreate, VmRequestPatch
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService


class VmRequestService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.requests = VmRequestRepository(session)
        self.audit = AuditService(session)
        self.notifications = NotificationService(session)

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
        await self.session.commit()
        await self.session.refresh(request)
        return request

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
        request = await self.requests.get(request_id)
        if not request:
            raise ApiError(404, "vm_request_not_found", "Demande VM introuvable.")
        if request.status != RequestStatus.approved:
            raise ApiError(409, "vm_request_not_approved", "Seule une demande approuvée peut passer en provisionnement.")
        request.status = RequestStatus.provisioning
        self.audit.record(
            "provisioning_requested",
            f"Provisionnement demandé pour la demande #{request_id}. Aucun appel Terraform n'est lancé par cette API.",
            actor_id=actor.id,
            request_id=request_id,
        )
        await self.session.commit()
        await self.session.refresh(request)
        return request
