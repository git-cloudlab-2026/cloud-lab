from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_session
from app.services.dashboard_service import DashboardService

router = APIRouter()


@router.get("/summary", response_model=dict)
async def summary(session: AsyncSession = Depends(get_session), _user=Depends(get_current_user)):
    return {"data": await DashboardService(session).summary()}
