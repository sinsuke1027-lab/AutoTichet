from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import CurrentUser
from src.db.engine import get_db
from src.db.models import UserProfile

router = APIRouter(prefix="/api/v1/users", tags=["users"])
DbDep = Annotated[AsyncSession, Depends(get_db)]


@router.get("/me")
async def get_me(current_user: CurrentUser) -> dict:
    return {
        "user_id": current_user.sub,
        "name": current_user.name,
        "email": current_user.email,
        "roles": current_user.roles,
    }


@router.get("")
async def list_users(db: DbDep, current_user: CurrentUser) -> list[dict]:
    result = await db.execute(select(UserProfile).order_by(UserProfile.display_name))
    return [
        {
            "user_id": u.user_id,
            "display_name": u.display_name,
            "email": u.email,
            "role": u.role,
            "capacity_hours_per_day": u.capacity_hours_per_day,
        }
        for u in result.scalars().all()
    ]
