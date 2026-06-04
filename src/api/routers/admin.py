# src/api/routers/admin.py
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import array as pg_array
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import TokenPayload, require_role
from src.db.engine import get_db
from src.db.models import DepartmentTag, UserProfile
from src.models.task_web import (
    AdminUserCreate,
    AdminUserResponse,
    AdminUserUpdate,
    DepartmentTagCreate,
    DepartmentTagResponse,
    DepartmentTagUpdate,
)

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


# --- タグ管理 ---


@router.get("/tags", response_model=list[DepartmentTagResponse])
async def list_tags(db: DbDep, _: AdminDep) -> list[DepartmentTagResponse]:
    result = await db.execute(select(DepartmentTag).order_by(DepartmentTag.name))
    return [DepartmentTagResponse.model_validate(t) for t in result.scalars().all()]


@router.post("/tags", response_model=DepartmentTagResponse, status_code=status.HTTP_201_CREATED)
async def create_tag(body: DepartmentTagCreate, db: DbDep, _: AdminDep) -> DepartmentTagResponse:
    existing = await db.execute(select(DepartmentTag).where(DepartmentTag.name == body.name))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="タグが既に存在します")
    tag = DepartmentTag(name=body.name, description=body.description)
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return DepartmentTagResponse.model_validate(tag)


@router.patch("/tags/{tag}", response_model=DepartmentTagResponse)
async def update_tag(
    tag: str, body: DepartmentTagUpdate, db: DbDep, _: AdminDep
) -> DepartmentTagResponse:
    result = await db.execute(select(DepartmentTag).where(DepartmentTag.name == tag))
    dept_tag = result.scalar_one_or_none()
    if dept_tag is None:
        raise HTTPException(status_code=404, detail="タグが見つかりません")

    new_name = body.new_name if body.new_name is not None else tag

    if new_name != tag:
        # タグ名変更: 全ユーザーの department_tags 配列も更新
        user_result = await db.execute(
            select(UserProfile).where(UserProfile.department_tags.op("@>")(pg_array([tag])))
        )
        for user in user_result.scalars().all():
            user.department_tags = [
                new_name if t == tag else t for t in (user.department_tags or [])
            ]
        # PK 変更のため DELETE + INSERT
        await db.delete(dept_tag)
        await db.flush()
        dept_tag = DepartmentTag(name=new_name, description=body.description)
        db.add(dept_tag)
    else:
        dept_tag.description = body.description

    await db.commit()
    # commit 後に re-fetch（expire 対策）
    refreshed = await db.execute(select(DepartmentTag).where(DepartmentTag.name == new_name))
    return DepartmentTagResponse.model_validate(refreshed.scalar_one())


@router.delete("/tags/{tag}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(tag: str, db: DbDep, _: AdminDep) -> None:
    # department_tags テーブルから削除（テーブルに存在しない場合はユーザー配列のみ処理・後方互換）
    tag_result = await db.execute(select(DepartmentTag).where(DepartmentTag.name == tag))
    dept_tag = tag_result.scalar_one_or_none()
    if dept_tag is not None:
        await db.delete(dept_tag)

    # 全ユーザーの department_tags 配列からも削除
    user_result = await db.execute(
        select(UserProfile).where(UserProfile.department_tags.op("@>")(pg_array([tag])))
    )
    for user in user_result.scalars().all():
        user.department_tags = [t for t in (user.department_tags or []) if t != tag]

    await db.commit()
