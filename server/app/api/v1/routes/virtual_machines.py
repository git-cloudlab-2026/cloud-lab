from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, require_roles
from app.db.session import get_session
from app.domain.enums import UserRole, VmStatus
from app.domain.models import User
from app.repositories.vms import VirtualMachineRepository, VmMetricRepository
from app.schemas.common import (
    DestructionResult,
    ProvisioningResult,
    VirtualMachinePatch,
    VirtualMachineRead,
    VmMetricCreate,
    VmMetricRead,
)
from app.services.vm_service import VirtualMachineService

router = APIRouter()


@router.get("", response_model=dict)
async def list_vms(status: VmStatus | None = None, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    owner_id = user.id if user.role == UserRole.student else None
    rows = await VirtualMachineRepository(session).list_filtered(status=status, owner_id=owner_id)
    return {"data": [VirtualMachineRead.model_validate(row) for row in rows]}


@router.get("/expired", response_model=dict)
async def list_expired_vms(session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    owner_id = user.id if user.role == UserRole.student else None
    rows = await VirtualMachineRepository(session).list_filtered(status=VmStatus.expired, owner_id=owner_id)
    return {"data": [VirtualMachineRead.model_validate(row) for row in rows]}


@router.get("/{vm_id}", response_model=dict)
async def get_vm(vm_id: int, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    row = await VirtualMachineService(session).get_visible_vm(vm_id, user)
    return {"data": VirtualMachineRead.model_validate(row)}


@router.post("/{vm_id}/destroy", response_model=dict)
async def destroy_vm(vm_id: int, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    row = await VirtualMachineService(session).destroy_with_provisioner(vm_id, user)
    return {"data": VirtualMachineRead.model_validate(row)}


@router.post("/{vm_id}/retry-ansible", response_model=dict)
async def retry_ansible(vm_id: int, session: AsyncSession = Depends(get_session), user: User = Depends(require_roles("admin", "validator"))):
    row = await VirtualMachineService(session).retry_ansible(vm_id, user)
    return {"data": VirtualMachineRead.model_validate(row)}


@router.patch("/{vm_id}", response_model=dict)
async def patch_vm(vm_id: int, payload: VirtualMachinePatch, session: AsyncSession = Depends(get_session), user: User = Depends(require_roles("admin", "validator"))):
    row = await VirtualMachineService(session).patch_status(vm_id, payload, user)
    return {"data": VirtualMachineRead.model_validate(row)}


@router.patch("/{vm_id}/provisioning-result", response_model=dict)
async def provisioning_result(vm_id: int, payload: ProvisioningResult, session: AsyncSession = Depends(get_session), user: User = Depends(require_roles("admin"))):
    row = await VirtualMachineService(session).provisioning_result(vm_id, payload, user)
    return {"data": VirtualMachineRead.model_validate(row)}


@router.patch("/{vm_id}/destruction-result", response_model=dict)
async def destruction_result(vm_id: int, payload: DestructionResult, session: AsyncSession = Depends(get_session), user: User = Depends(require_roles("admin"))):
    row = await VirtualMachineService(session).destruction_result(vm_id, payload, user)
    return {"data": VirtualMachineRead.model_validate(row)}


@router.post("/{vm_id}/metrics", response_model=dict, status_code=201)
async def create_metric(vm_id: int, payload: VmMetricCreate, session: AsyncSession = Depends(get_session), _user=Depends(require_roles("admin", "validator"))):
    row = await VirtualMachineService(session).add_metric(vm_id, payload)
    return {"data": VmMetricRead.model_validate(row)}


@router.get("/{vm_id}/metrics/history", response_model=dict)
async def metric_history(vm_id: int, limit: int = 50, session: AsyncSession = Depends(get_session), _user=Depends(get_current_user)):
    rows = await VmMetricRepository(session).history_for_vm(vm_id, limit)
    return {"data": [VmMetricRead.model_validate(row) for row in rows]}
