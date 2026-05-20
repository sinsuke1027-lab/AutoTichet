# src/api/routers/admin.py
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import TokenPayload, require_role
from src.db.engine import get_db
from src.db.models import UserProfile
from src.models.task_web import AdminUserCreate, AdminUserResponse, AdminUserUpdate

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
AdminDep = Annotated[TokenPayload, Depends(require_role("admin"))]


@router.get("/users", response_model=list[AdminUserResponse])
async def list_admin_users(db: DbDep, _: AdminDep) -> list[AdminUserResponse]:
    result = await db.execute(select(UserProfile))
    return [AdminUserResponse.model_validate(u) for u in result.scalars().all()]


@router.post("/users", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
async def create_admin_user(body: AdminUserCreate, db: DbDep, _: AdminDep) -> AdminUserResponse:
    existing = await db.execute(select(UserProfile).where(UserProfile.user_id == body.user_id))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="ユーザーが既に存在します")
    user = UserProfile(
        user_id=body.user_id,
        display_name=body.display_name,
        email=body.email,
        role=body.role,
        department_tags=body.department_tags,
        capacity_hours_per_day=body.capacity_hours_per_day,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return AdminUserResponse.model_validate(user)


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
async def update_admin_user(
    user_id: str, body: AdminUserUpdate, db: DbDep, _: AdminDep
) -> AdminUserResponse:
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return AdminUserResponse.model_validate(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_admin_user(user_id: str, db: DbDep, _: AdminDep) -> None:
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
    await db.delete(user)
    await db.commit()
