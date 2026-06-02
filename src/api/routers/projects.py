import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import ROLE_HIERARCHY, CurrentUser, require_role
from src.db.engine import get_db
from src.db.models import Project
from src.models.task_web import ProjectResponse, ProjectUpdate

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

DbDep = Annotated[AsyncSession, Depends(get_db)]


class _ProjectCreate(ProjectUpdate):
    """リクエストボディ用モデル。created_by はサーバー側でセットするため除外。"""

    name: str


def _check_project_permission(project: Project, current_user: CurrentUser) -> None:
    """作成者または leader 以上でなければ 403 を発生させる。"""
    user_role = max((ROLE_HIERARCHY.get(r, 0) for r in current_user.roles), default=0)
    if project.created_by != current_user.sub and user_role < ROLE_HIERARCHY["leader"]:
        raise HTTPException(status_code=403, detail="このプロジェクトを操作する権限がありません")


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    db: DbDep,
    current_user: CurrentUser,
    include_archived: bool = Query(default=False),
) -> list[ProjectResponse]:
    query = select(Project).order_by(Project.created_at.desc())
    if not include_archived:
        query = query.where(Project.status != "archived")
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
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}/archive", response_model=ProjectResponse)
async def archive_project(
    project_id: uuid.UUID, db: DbDep, current_user: CurrentUser
) -> ProjectResponse:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="プロジェクトが見つかりません")
    _check_project_permission(project, current_user)
    project.status = "archived"
    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}/unarchive", response_model=ProjectResponse)
async def unarchive_project(
    project_id: uuid.UUID, db: DbDep, current_user: CurrentUser
) -> ProjectResponse:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="プロジェクトが見つかりません")
    _check_project_permission(project, current_user)
    project.status = "active"
    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


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
