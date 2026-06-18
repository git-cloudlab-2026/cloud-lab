from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, require_roles
from app.db.session import get_session
from app.domain.models import User
from app.repositories.users import UserRepository
from app.schemas.common import UserCreate, UserRead

router = APIRouter()


@router.get("", response_model=dict)
async def list_users(session: AsyncSession = Depends(get_session), _user: User = Depends(get_current_user)):
    users = await UserRepository(session).list(limit=500)
    return {"data": [UserRead.model_validate(user) for user in users]}


@router.post("", response_model=dict, status_code=201)
async def create_user(payload: UserCreate, session: AsyncSession = Depends(get_session), _admin: User = Depends(require_roles("admin"))):
    user = User(**payload.model_dump())
    UserRepository(session).add(user)
    await session.commit()
    await session.refresh(user)
    return {"data": UserRead.model_validate(user)}
