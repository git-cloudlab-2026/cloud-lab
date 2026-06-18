from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_session
from app.repositories.catalog import CourseRepository, VmTemplateRepository
from app.repositories.vms import CostRecordRepository, VmMetricRepository
from app.schemas.common import CostRecordRead, CourseRead, VmMetricRead, VmTemplateRead

router = APIRouter()


@router.get("/courses", response_model=dict)
async def courses(session: AsyncSession = Depends(get_session), _user=Depends(get_current_user)):
    rows = await CourseRepository(session).list(limit=500)
    return {"data": [CourseRead.model_validate(row) for row in rows]}


@router.get("/vm-templates", response_model=dict)
async def vm_templates(session: AsyncSession = Depends(get_session), _user=Depends(get_current_user)):
    rows = await VmTemplateRepository(session).list_active()
    return {"data": [VmTemplateRead.model_validate(row) for row in rows]}


@router.get("/vm-metrics", response_model=dict)
async def vm_metrics(limit: int = 100, session: AsyncSession = Depends(get_session), _user=Depends(get_current_user)):
    rows = await VmMetricRepository(session).list_global(limit=limit)
    return {"data": [VmMetricRead.model_validate(row) for row in rows]}


@router.get("/cost-records", response_model=dict)
async def cost_records(session: AsyncSession = Depends(get_session), _user=Depends(get_current_user)):
    rows = await CostRecordRepository(session).list(limit=500)
    return {"data": [CostRecordRead.model_validate(row) for row in rows]}
