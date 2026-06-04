from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import CurrentUser
from src.api.routers._scope import visible_user_ids as _visible_user_ids
from src.db.engine import get_db
from src.db.models import UserProfile
from src.models.task_web import AdminUserResponse, MeResponse, UserProfileUpdate, UserResponse

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


@router.get("/me/profile", response_model=AdminUserResponse)
async def get_my_profile(db: DbDep, current_user: CurrentUser) -> AdminUserResponse:
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == current_user.sub))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="プロフィールが見つかりません")
    return AdminUserResponse.model_validate(profile)


@router.patch("/me", response_model=AdminUserResponse)
async def update_my_profile(
    body: UserProfileUpdate, db: DbDep, current_user: CurrentUser
) -> AdminUserResponse:
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == current_user.sub))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="プロフィールが見つかりません")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    await db.commit()
    await db.refresh(profile)
    return AdminUserResponse.model_validate(profile)


@router.get("", response_model=list[AdminUserResponse])
async def list_users(
    db: DbDep,
    current_user: CurrentUser,
    scope: str = Query(default="all"),  # "all" | "visible"
) -> list[AdminUserResponse]:
    query = select(UserProfile).order_by(UserProfile.display_name)
    if scope == "visible":
        allowed_uids = await _visible_user_ids(db, current_user)
        if allowed_uids is not None:
            query = query.where(UserProfile.user_id.in_(allowed_uids))
    result = await db.execute(query)
    return [AdminUserResponse.model_validate(u) for u in result.scalars().all()]
