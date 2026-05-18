import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import CurrentUser, require_role
from src.db.engine import get_db
from src.db.models import Project
from src.models.task_web import ProjectResponse, ProjectUpdate

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

DbDep = Annotated[AsyncSession, Depends(get_db)]


class _ProjectCreate(ProjectUpdate):
    """リクエストボディ用モデル。created_by はサーバー側でセットするため除外。"""

    name: str


@router.get("", response_model=list[ProjectResponse])
async def list_projects(db: DbDep, current_user: CurrentUser) -> list[ProjectResponse]:
    result = await db.execute(select(Project).order_by(Project.created_at.desc()))
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
