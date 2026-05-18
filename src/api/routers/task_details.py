import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import CurrentUser
from src.db.engine import get_db
from src.db.models import Task, TaskComment, TaskDependency, TaskWorkHour
from src.models.task_web import (
    CommentCreate,
    CommentResponse,
    WorkHourCreate,
    WorkHourResponse,
)

router = APIRouter(prefix="/api/v1/tasks", tags=["task-details"])
DbDep = Annotated[AsyncSession, Depends(get_db)]


async def _get_task_or_404(task_id: uuid.UUID, db: AsyncSession) -> Task:
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="タスクが見つかりません")
    return task


# --- コメント ---


@router.get("/{task_id}/comments", response_model=list[CommentResponse])
async def list_comments(
    task_id: uuid.UUID, db: DbDep, current_user: CurrentUser
) -> list[CommentResponse]:
    await _get_task_or_404(task_id, db)
    result = await db.execute(
        select(TaskComment)
        .where(TaskComment.task_id == task_id)
        .order_by(TaskComment.created_at.asc())
    )
    return [CommentResponse.model_validate(c) for c in result.scalars().all()]


@router.post("/{task_id}/comments", response_model=CommentResponse, status_code=201)
async def create_comment(
    task_id: uuid.UUID, body: CommentCreate, db: DbDep, current_user: CurrentUser
) -> CommentResponse:
    await _get_task_or_404(task_id, db)
    comment = TaskComment(
        task_id=task_id,
        author_id=current_user.sub,
        content=body.content,
        mentions=body.mentions,
        sharepoint_links=body.sharepoint_links,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return CommentResponse.model_validate(comment)


# --- 工数 ---


@router.get("/{task_id}/work-hours", response_model=list[WorkHourResponse])
async def list_work_hours(
    task_id: uuid.UUID, db: DbDep, current_user: CurrentUser
) -> list[WorkHourResponse]:
    await _get_task_or_404(task_id, db)
    result = await db.execute(
        select(TaskWorkHour)
        .where(TaskWorkHour.task_id == task_id)
        .order_by(TaskWorkHour.recorded_at.desc())
    )
    return [WorkHourResponse.model_validate(wh) for wh in result.scalars().all()]


@router.post("/{task_id}/work-hours", response_model=WorkHourResponse, status_code=201)
async def create_work_hour(
    task_id: uuid.UUID, body: WorkHourCreate, db: DbDep, current_user: CurrentUser
) -> WorkHourResponse:
    await _get_task_or_404(task_id, db)
    wh = TaskWorkHour(
        task_id=task_id,
        user_id=current_user.sub,
        estimated_hours=body.estimated_hours,
        actual_hours=body.actual_hours,
        notes=body.notes,
    )
    db.add(wh)
    await db.commit()
    await db.refresh(wh)
    return WorkHourResponse.model_validate(wh)


# --- 依存関係 ---


@router.get("/{task_id}/dependencies")
async def list_dependencies(task_id: uuid.UUID, db: DbDep, current_user: CurrentUser) -> list[dict]:
    result = await db.execute(select(TaskDependency).where(TaskDependency.task_id == task_id))
    return [
        {"id": str(d.id), "depends_on_task_id": str(d.depends_on_task_id)}
        for d in result.scalars().all()
    ]


@router.post("/{task_id}/dependencies", status_code=201)
async def create_dependency(
    task_id: uuid.UUID,
    depends_on_task_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUser,
) -> dict:
    await _get_task_or_404(task_id, db)
    await _get_task_or_404(depends_on_task_id, db)
    dep = TaskDependency(task_id=task_id, depends_on_task_id=depends_on_task_id)
    db.add(dep)
    await db.commit()
    await db.refresh(dep)
    return {"id": str(dep.id), "depends_on_task_id": str(dep.depends_on_task_id)}


@router.delete("/{task_id}/dependencies/{dep_id}", status_code=204)
async def delete_dependency(
    task_id: uuid.UUID, dep_id: uuid.UUID, db: DbDep, current_user: CurrentUser
) -> None:
    result = await db.execute(
        select(TaskDependency).where(TaskDependency.id == dep_id, TaskDependency.task_id == task_id)
    )
    dep = result.scalar_one_or_none()
    if dep is None:
        raise HTTPException(status_code=404, detail="依存関係が見つかりません")
    await db.delete(dep)
    await db.commit()
