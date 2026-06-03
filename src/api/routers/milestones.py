import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import ROLE_HIERARCHY, CurrentUser
from src.db.engine import get_db
from src.db.models import Milestone, Project
from src.models.task_web import MilestoneCreate, MilestoneResponse, MilestoneUpdate

router = APIRouter(prefix="/api/v1/projects", tags=["milestones"])

DbDep = Annotated[AsyncSession, Depends(get_db)]


async def _get_project_or_404(project_id: uuid.UUID, db: AsyncSession) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="プロジェクトが見つかりません")
    return project


def _check_permission(project: Project, current_user: CurrentUser) -> None:
    user_role = max((ROLE_HIERARCHY.get(r, 0) for r in current_user.roles), default=0)
    if project.created_by != current_user.sub and user_role < ROLE_HIERARCHY["leader"]:
        raise HTTPException(status_code=403, detail="このプロジェクトを操作する権限がありません")


@router.get("/{project_id}/milestones", response_model=list[MilestoneResponse])
async def list_milestones(
    project_id: uuid.UUID, db: DbDep, current_user: CurrentUser
) -> list[MilestoneResponse]:
    await _get_project_or_404(project_id, db)
    result = await db.execute(
        select(Milestone)
        .where(Milestone.project_id == project_id)
        .order_by(Milestone.due_date.asc())
    )
    return [MilestoneResponse.model_validate(m) for m in result.scalars().all()]


@router.post(
    "/{project_id}/milestones",
    response_model=MilestoneResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_milestone(
    project_id: uuid.UUID, body: MilestoneCreate, db: DbDep, current_user: CurrentUser
) -> MilestoneResponse:
    project = await _get_project_or_404(project_id, db)
    _check_permission(project, current_user)
    milestone = Milestone(
        id=uuid.uuid4(),
        project_id=project_id,
        title=body.title,
        due_date=body.due_date,
        completed=False,
    )
    db.add(milestone)
    await db.commit()
    await db.refresh(milestone)
    return MilestoneResponse.model_validate(milestone)


@router.put("/{project_id}/milestones/{milestone_id}", response_model=MilestoneResponse)
async def update_milestone(
    project_id: uuid.UUID,
    milestone_id: uuid.UUID,
    body: MilestoneUpdate,
    db: DbDep,
    current_user: CurrentUser,
) -> MilestoneResponse:
    project = await _get_project_or_404(project_id, db)
    _check_permission(project, current_user)
    result = await db.execute(
        select(Milestone).where(Milestone.id == milestone_id, Milestone.project_id == project_id)
    )
    milestone = result.scalar_one_or_none()
    if milestone is None:
        raise HTTPException(status_code=404, detail="マイルストーンが見つかりません")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(milestone, field, value)
    await db.commit()
    await db.refresh(milestone)
    return MilestoneResponse.model_validate(milestone)


@router.patch("/{project_id}/milestones/{milestone_id}/complete", response_model=MilestoneResponse)
async def toggle_milestone_complete(
    project_id: uuid.UUID,
    milestone_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUser,
) -> MilestoneResponse:
    project = await _get_project_or_404(project_id, db)
    _check_permission(project, current_user)
    result = await db.execute(
        select(Milestone).where(Milestone.id == milestone_id, Milestone.project_id == project_id)
    )
    milestone = result.scalar_one_or_none()
    if milestone is None:
        raise HTTPException(status_code=404, detail="マイルストーンが見つかりません")
    if milestone.completed:
        milestone.completed = False
        milestone.completed_at = None
    else:
        milestone.completed = True
        milestone.completed_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(milestone)
    return MilestoneResponse.model_validate(milestone)


@router.delete(
    "/{project_id}/milestones/{milestone_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_milestone(
    project_id: uuid.UUID,
    milestone_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUser,
) -> None:
    project = await _get_project_or_404(project_id, db)
    _check_permission(project, current_user)
    result = await db.execute(
        select(Milestone).where(Milestone.id == milestone_id, Milestone.project_id == project_id)
    )
    milestone = result.scalar_one_or_none()
    if milestone is None:
        raise HTTPException(status_code=404, detail="マイルストーンが見つかりません")
    await db.delete(milestone)
    await db.commit()
