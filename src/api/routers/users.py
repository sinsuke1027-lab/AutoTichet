from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import CurrentUser
from src.db.engine import get_db
from src.db.models import UserProfile
from src.models.task_web import MeResponse, UserResponse

router = APIRouter(prefix="/api/v1/users", tags=["users"])
DbDep = Annotated[AsyncSession, Depends(get_db)]


@router.get("/me", response_model=MeResponse)
async def get_me(current_user: CurrentUser) -> MeResponse:
    return MeResponse(
        user_id=current_user.sub,
        name=current_user.name,
        email=current_user.email,
        roles=current_user.roles,
    )


@router.get("", response_model=list[UserResponse])
async def list_users(
    db: DbDep,
    current_user: CurrentUser,
) -> list[UserResponse]:
    result = await db.execute(select(UserProfile).order_by(UserProfile.display_name))
    return [UserResponse.model_validate(u) for u in result.scalars().all()]
