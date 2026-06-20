from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, require_roles
from app.db.session import get_session
from app.domain.enums import RequestStatus, UserRole
from app.domain.models import User
from app.repositories.vm_requests import VmRequestRepository
from app.schemas.common import VmRequestCreate, VmRequestPatch, VmRequestRead, VmRequestReject
from app.services.vm_request_service import VmRequestService

router = APIRouter()


@router.get("", response_model=dict)
async def list_requests(status: RequestStatus | None = None, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    requester_id = user.id if user.role == UserRole.student else None
    rows = await VmRequestRepository(session).list_filtered(status=status, requester_id=requester_id)
    return {"data": [VmRequestRead.model_validate(row) for row in rows]}


@router.post("", response_model=dict, status_code=201)
async def create_request(payload: VmRequestCreate, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    row = await VmRequestService(session).create(payload, user)
    return {"data": VmRequestRead.model_validate(row)}


@router.patch("/{request_id}", response_model=dict)
async def patch_request(
    request_id: int,
    payload: VmRequestPatch,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_roles("validator", "admin")),
):
    row = await VmRequestService(session).patch(request_id, payload, user)
    return {"data": VmRequestRead.model_validate(row)}


@router.post("/{request_id}/provision", response_model=dict, status_code=202)
async def request_provision(
    request_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_roles("validator", "admin")),
):
    row = await VmRequestService(session).mark_provisioning_requested(request_id, user)
    return {"data": VmRequestRead.model_validate(row)}


@router.post("/{request_id}/approve", response_model=dict)
async def approve_request(
    request_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_roles("admin", "validator")),
):
    row = await VmRequestService(session).approve_and_provision(request_id, user)
    return {"data": VmRequestRead.model_validate(row)}


@router.post("/{request_id}/reject", response_model=dict)
async def reject_request(
    request_id: int,
    payload: VmRequestReject,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_roles("admin", "validator")),
):
    row = await VmRequestService(session).reject(request_id, payload.reason, user)
    return {"data": VmRequestRead.model_validate(row)}
