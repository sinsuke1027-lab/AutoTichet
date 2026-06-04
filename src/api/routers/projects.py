import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import ROLE_HIERARCHY, CurrentUser, require_role
from src.db.engine import get_db
from src.db.models import Project, ProjectMember
from src.models.task_web import (
    ProjectMemberAdd,
    ProjectMemberResponse,
    ProjectResponse,
    ProjectUpdate,
)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

DbDep = Annotated[AsyncSession, Depends(get_db)]


class _ProjectCreate(ProjectUpdate):
    """リクエストボディ用モデル。created_by はサーバー側でセットするため除外。"""

    name: str
    member_ids: list[str] = Field(default_factory=list)


def _check_project_permission(project: Project, current_user: CurrentUser) -> None:
    """作成者または leader 以上でなければ 403 を発生させる。"""
    user_role = max((ROLE_HIERARCHY.get(r, 0) for r in current_user.roles), default=0)
    if project.created_by != current_user.sub and user_role < ROLE_HIERARCHY["leader"]:
        raise HTTPException(status_code=403, detail="このプロジェクトを操作する権限がありません")


async def _assert_owner_or_admin(
    project_id: uuid.UUID, db: AsyncSession, current_user: CurrentUser
) -> None:
    user_role = max((ROLE_HIERARCHY.get(r, 0) for r in current_user.roles), default=0)
    if user_role >= ROLE_HIERARCHY["admin"]:
        return
    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == current_user.sub,
            ProjectMember.role == "owner",
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=403, detail="プロジェクトオーナーまたは管理者のみ操作できます"
        )


async def _set_project_status(
    project_id: uuid.UUID,
    new_status: str,
    db: AsyncSession,
    current_user: CurrentUser,
) -> ProjectResponse:
    """プロジェクトのステータスを更新するヘルパー関数。"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="プロジェクトが見つかりません")
    _check_project_permission(project, current_user)
    project.status = new_status
    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    db: DbDep,
    current_user: CurrentUser,
    include_archived: bool = Query(default=False),
    scope: str = Query(default="mine"),
) -> list[ProjectResponse]:
    user_role = max((ROLE_HIERARCHY.get(r, 0) for r in current_user.roles), default=0)
    query = select(Project).order_by(Project.created_at.desc())
    if not include_archived:
        query = query.where(Project.status != "archived")
    if scope == "mine" and user_role < ROLE_HIERARCHY["admin"]:
        # project_members に登録済み OR 自分が作成者
        query = query.where(
            or_(
                Project.id.in_(
                    select(ProjectMember.project_id).where(
                        ProjectMember.user_id == current_user.sub
                    )
                ),
                Project.created_by == current_user.sub,
            )
        )
    result = await db.execute(query)
    return [ProjectResponse.model_validate(p) for p in result.scalars().all()]


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: _ProjectCreate, db: DbDep, current_user: CurrentUser
) -> ProjectResponse:
    project = Project(
        name=body.name,
        description=body.description,
        status=body.status or "active",
        created_by=current_user.sub,
    )
    db.add(project)
    await db.flush()
    db.add(ProjectMember(project_id=project.id, user_id=current_user.sub, role="owner"))
    for uid in body.member_ids:
        if uid != current_user.sub:
            db.add(ProjectMember(project_id=project.id, user_id=uid, role="member"))
    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID, db: DbDep, current_user: CurrentUser
) -> ProjectResponse:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="プロジェクトが見つかりません")
    return ProjectResponse.model_validate(project)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID, body: ProjectUpdate, db: DbDep, current_user: CurrentUser
) -> ProjectResponse:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="プロジェクトが見つかりません")
    _check_project_permission(project, current_user)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}/archive", response_model=ProjectResponse)
async def archive_project(
    project_id: uuid.UUID, db: DbDep, current_user: CurrentUser
) -> ProjectResponse:
    return await _set_project_status(project_id, "archived", db, current_user)


@router.patch("/{project_id}/unarchive", response_model=ProjectResponse)
async def unarchive_project(
    project_id: uuid.UUID, db: DbDep, current_user: CurrentUser
) -> ProjectResponse:
    return await _set_project_status(project_id, "active", db, current_user)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    db: DbDep,
    current_user: Annotated[CurrentUser, Depends(require_role("leader"))],
) -> None:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="プロジェクトが見つかりません")
    await db.delete(project)
    await db.commit()


@router.get("/{project_id}/members", response_model=list[ProjectMemberResponse])
async def list_project_members(
    project_id: uuid.UUID, db: DbDep, current_user: CurrentUser
) -> list[ProjectMemberResponse]:
    result = await db.execute(
        select(ProjectMember)
        .where(ProjectMember.project_id == project_id)
        .order_by(ProjectMember.joined_at)
    )
    return [ProjectMemberResponse.model_validate(m) for m in result.scalars().all()]


@router.post(
    "/{project_id}/members",
    response_model=ProjectMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_project_member(
    project_id: uuid.UUID,
    body: ProjectMemberAdd,
    db: DbDep,
    current_user: CurrentUser,
) -> ProjectMemberResponse:
    await _assert_owner_or_admin(project_id, db, current_user)
    exists = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == body.user_id,
        )
    )
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="既にメンバーに追加されています")
    member = ProjectMember(project_id=project_id, user_id=body.user_id, role=body.role)
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return ProjectMemberResponse.model_validate(member)


@router.delete("/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_project_member(
    project_id: uuid.UUID,
    user_id: str,
    db: DbDep,
    current_user: CurrentUser,
) -> None:
    await _assert_owner_or_admin(project_id, db, current_user)
    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="メンバーが見つかりません")
    await db.delete(member)
    await db.commit()
