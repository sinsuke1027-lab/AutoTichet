import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import CurrentUser
from src.db.engine import get_db
from src.db.models import Task, TaskAssignee, TaskComment, TaskDependency, TaskWorkHour
from src.models.task_web import (
    CommentCreate,
    CommentResponse,
    DependencyCreate,
    DependencyResponse,
    TaskAssigneeCreate,
    TaskAssigneeResponse,
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


@router.get("/{task_id}/dependencies", response_model=list[DependencyResponse])
async def list_dependencies(
    task_id: uuid.UUID, db: DbDep, current_user: CurrentUser
) -> list[DependencyResponse]:
    await _get_task_or_404(task_id, db)
    result = await db.execute(select(TaskDependency).where(TaskDependency.task_id == task_id))
    return [DependencyResponse.model_validate(d) for d in result.scalars().all()]


@router.post("/{task_id}/dependencies", response_model=DependencyResponse, status_code=201)
async def create_dependency(
    task_id: uuid.UUID, body: DependencyCreate, db: DbDep, current_user: CurrentUser
) -> DependencyResponse:
    if task_id == body.depends_on_task_id:
        raise HTTPException(status_code=422, detail="タスクは自分自身に依存できません")
    await _get_task_or_404(task_id, db)
    await _get_task_or_404(body.depends_on_task_id, db)
    dep = TaskDependency(task_id=task_id, depends_on_task_id=body.depends_on_task_id)
    db.add(dep)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="この依存関係はすでに存在します") from exc
    await db.refresh(dep)
    return DependencyResponse.model_validate(dep)


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


# --- 担当者（サブ） ---


@router.get("/{task_id}/assignees", response_model=list[TaskAssigneeResponse])
async def list_assignees(
    task_id: uuid.UUID, db: DbDep, current_user: CurrentUser
) -> list[TaskAssigneeResponse]:
    await _get_task_or_404(task_id, db)
    result = await db.execute(select(TaskAssignee).where(TaskAssignee.task_id == task_id))
    return [TaskAssigneeResponse.model_validate(a) for a in result.scalars().all()]


@router.post("/{task_id}/assignees", response_model=TaskAssigneeResponse, status_code=201)
async def add_assignee(
    task_id: uuid.UUID, body: TaskAssigneeCreate, db: DbDep, current_user: CurrentUser
) -> TaskAssigneeResponse:
    await _get_task_or_404(task_id, db)
    assignee = TaskAssignee(task_id=task_id, user_id=body.user_id, role=body.role)
    db.add(assignee)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="この担当者はすでに登録されています") from exc
    await db.refresh(assignee)
    return TaskAssigneeResponse.model_validate(assignee)


@router.delete("/{task_id}/assignees/{user_id}", status_code=204)
async def remove_assignee(
    task_id: uuid.UUID, user_id: str, db: DbDep, current_user: CurrentUser
) -> None:
    result = await db.execute(
        select(TaskAssignee).where(TaskAssignee.task_id == task_id, TaskAssignee.user_id == user_id)
    )
    assignee = result.scalar_one_or_none()
    if assignee is None:
        raise HTTPException(status_code=404, detail="担当者が見つかりません")
    await db.delete(assignee)
    await db.commit()
