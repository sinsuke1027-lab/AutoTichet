import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.auth import CurrentUser
from src.db.engine import get_db
from src.db.models import Task, TaskTag
from src.models.task_web import (
    TaskCreate,
    TaskListResponse,
    TaskResponse,
    TaskStatus,
    TaskUpdate,
)

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])

DbDep = Annotated[AsyncSession, Depends(get_db)]


def _task_to_response(task: Task) -> TaskResponse:
    tags = [t.tag for t in task.tags] if task.tags else []
    return TaskResponse(
        id=task.id,
        project_id=task.project_id,
        parent_task_id=task.parent_task_id,
        title=task.title,
        description=task.description,
        status=TaskStatus(task.status),
        priority=task.priority,
        assignee_id=task.assignee_id,
        due_date=task.due_date,
        start_date=task.start_date,
        visibility=task.visibility,
        source_type=task.source_type,
        confidence_score=task.confidence_score,
        route=task.route,
        created_by=task.created_by,
        created_at=task.created_at,
        updated_at=task.updated_at,
        tags=tags,
    )


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    db: DbDep,
    current_user: CurrentUser,
    status_filter: TaskStatus | None = Query(default=None, alias="status"),  # noqa: B008
    assignee: str | None = None,
    project_id: uuid.UUID | None = None,
    tag: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
) -> TaskListResponse:
    q = select(Task).options(selectinload(Task.tags))
    if status_filter:
        q = q.where(Task.status == status_filter.value)
    if assignee:
        q = q.where(Task.assignee_id == assignee)
    if project_id:
        q = q.where(Task.project_id == project_id)
    if tag:
        q = q.where(Task.id.in_(select(TaskTag.task_id).where(TaskTag.tag == tag)))

    count_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = count_result.scalar_one()

    result = await db.execute(
        q.order_by(Task.due_date.asc().nulls_last()).limit(limit).offset(offset)
    )
    items = [_task_to_response(t) for t in result.scalars().all()]
    return TaskListResponse(items=items, total=total)


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(body: TaskCreate, db: DbDep, current_user: CurrentUser) -> TaskResponse:
    tags = body.tags
    data = body.model_dump(exclude={"tags"})
    data["created_by"] = current_user.sub
    task = Task(**data)
    db.add(task)
    await db.flush()
    for tag in tags:
        db.add(TaskTag(task_id=task.id, tag=tag))
    await db.commit()
    await db.refresh(task, ["tags"])
    return _task_to_response(task)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: uuid.UUID, db: DbDep, current_user: CurrentUser) -> TaskResponse:
    result = await db.execute(
        select(Task).where(Task.id == task_id).options(selectinload(Task.tags))
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="タスクが見つかりません")
    return _task_to_response(task)


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: uuid.UUID, body: TaskUpdate, db: DbDep, current_user: CurrentUser
) -> TaskResponse:
    result = await db.execute(
        select(Task).where(Task.id == task_id).options(selectinload(Task.tags))
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="タスクが見つかりません")
    for field, value in body.model_dump(exclude_unset=True, exclude={"tags"}).items():
        setattr(task, field, value)
    if body.tags is not None:
        for existing in list(task.tags):
            await db.delete(existing)
        await db.flush()  # flush deletes before inserting new tags
        for tag in body.tags:
            db.add(TaskTag(task_id=task.id, tag=tag))
    await db.commit()
    await db.refresh(task, ["tags"])
    return _task_to_response(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: uuid.UUID, db: DbDep, current_user: CurrentUser) -> None:
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="タスクが見つかりません")
    await db.delete(task)
    await db.commit()


@router.get("/{task_id}/subtasks", response_model=list[TaskResponse])
async def list_subtasks(
    task_id: uuid.UUID, db: DbDep, current_user: CurrentUser
) -> list[TaskResponse]:
    result = await db.execute(
        select(Task).where(Task.parent_task_id == task_id).options(selectinload(Task.tags))
    )
    return [_task_to_response(t) for t in result.scalars().all()]
