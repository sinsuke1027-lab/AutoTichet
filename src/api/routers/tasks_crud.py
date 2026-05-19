import uuid
from collections import deque
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.auth import CurrentUser
from src.db.engine import get_db
from src.db.models import Task, TaskAssignee, TaskDependency, TaskTag
from src.models.task_web import (
    RescheduleRequest,
    RescheduleResponse,
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
    sub_assignees = [a.user_id for a in task.sub_assignees] if task.sub_assignees else []
    return TaskResponse(
        id=task.id,
        project_id=task.project_id,
        parent_task_id=task.parent_task_id,
        section_id=task.section_id,
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
        completed_at=task.completed_at,
        order_index=task.order_index,
        created_by=task.created_by,
        created_at=task.created_at,
        updated_at=task.updated_at,
        tags=tags,
        sub_assignees=sub_assignees,
    )


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    db: DbDep,
    current_user: CurrentUser,
    status_filter: TaskStatus | None = Query(default=None, alias="status"),  # noqa: B008
    assignee: str | None = None,
    project_id: uuid.UUID | None = None,
    section_id: uuid.UUID | None = None,
    tag: str | None = None,
    q: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    due_date_gte: date | None = Query(default=None),
    due_date_lte: date | None = Query(default=None),
    assignee_ids: list[str] | None = Query(default=None),
) -> TaskListResponse:
    query = select(Task).options(selectinload(Task.tags), selectinload(Task.sub_assignees))
    if status_filter:
        query = query.where(Task.status == status_filter.value)
    if assignee:
        query = query.where(Task.assignee_id == assignee)
    if project_id:
        query = query.where(Task.project_id == project_id)
    if section_id:
        query = query.where(Task.section_id == section_id)
    if tag:
        query = query.where(Task.id.in_(select(TaskTag.task_id).where(TaskTag.tag == tag)))
    if q:
        like = f"%{q}%"
        query = query.where(Task.title.ilike(like) | Task.description.ilike(like))
    if due_date_gte:
        query = query.where(Task.due_date >= due_date_gte)
    if due_date_lte:
        query = query.where(Task.due_date <= due_date_lte)
    if assignee_ids:
        query = query.where(Task.assignee_id.in_(assignee_ids))

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()

    result = await db.execute(
        query.order_by(Task.due_date.asc().nulls_last()).limit(limit).offset(offset)
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
    await db.refresh(task, ["tags", "sub_assignees"])
    return _task_to_response(task)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: uuid.UUID, db: DbDep, current_user: CurrentUser) -> TaskResponse:
    result = await db.execute(
        select(Task)
        .where(Task.id == task_id)
        .options(selectinload(Task.tags), selectinload(Task.sub_assignees))
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
        select(Task)
        .where(Task.id == task_id)
        .options(selectinload(Task.tags), selectinload(Task.sub_assignees))
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
    await db.refresh(task, ["tags", "sub_assignees"])
    return _task_to_response(task)


@router.post(
    "/{task_id}/duplicate", response_model=TaskResponse, status_code=status.HTTP_201_CREATED
)
async def duplicate_task(task_id: uuid.UUID, db: DbDep, current_user: CurrentUser) -> TaskResponse:
    result = await db.execute(
        select(Task)
        .where(Task.id == task_id)
        .options(selectinload(Task.tags), selectinload(Task.sub_assignees))
    )
    original = result.scalar_one_or_none()
    if original is None:
        raise HTTPException(status_code=404, detail="タスクが見つかりません")

    new_task = Task(
        title=f"{original.title}（コピー）",
        description=original.description,
        status="not_started",
        priority=original.priority,
        assignee_id=original.assignee_id,
        due_date=original.due_date,
        start_date=original.start_date,
        visibility=original.visibility,
        project_id=original.project_id,
        section_id=original.section_id,
        parent_task_id=original.parent_task_id,
        created_by=current_user.sub,
        completed_at=None,
        order_index=original.order_index,
    )
    db.add(new_task)
    await db.flush()
    for tag_obj in original.tags:
        db.add(TaskTag(task_id=new_task.id, tag=tag_obj.tag))
    for sa_obj in original.sub_assignees:
        db.add(TaskAssignee(task_id=new_task.id, user_id=sa_obj.user_id, role=sa_obj.role))
    await db.commit()
    await db.refresh(new_task, ["tags", "sub_assignees"])
    return _task_to_response(new_task)


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
        select(Task)
        .where(Task.parent_task_id == task_id)
        .options(selectinload(Task.tags), selectinload(Task.sub_assignees))
    )
    return [_task_to_response(t) for t in result.scalars().all()]


async def _cascade_reschedule(db: AsyncSession, root_id: uuid.UUID, delta: timedelta) -> list[Task]:
    """依存タスクを BFS で走査して日程を連鎖移動する。"""
    updated: list[Task] = []
    queue: deque[uuid.UUID] = deque([root_id])
    visited: set[uuid.UUID] = {root_id}
    while queue:
        current_id = queue.popleft()
        dep_result = await db.execute(
            select(TaskDependency).where(TaskDependency.depends_on_task_id == current_id)
        )
        for dep in dep_result.scalars().all():
            if dep.task_id in visited:
                continue
            visited.add(dep.task_id)
            task_result = await db.execute(
                select(Task)
                .where(Task.id == dep.task_id)
                .options(selectinload(Task.tags), selectinload(Task.sub_assignees))
            )
            task = task_result.scalar_one_or_none()
            if task and task.due_date:
                if task.start_date:
                    task.start_date = task.start_date + delta
                task.due_date = task.due_date + delta
                updated.append(task)
                queue.append(dep.task_id)
    return updated


@router.post("/{task_id}/reschedule", response_model=RescheduleResponse)
async def reschedule_task(
    task_id: uuid.UUID, body: RescheduleRequest, db: DbDep, current_user: CurrentUser
) -> RescheduleResponse:
    result = await db.execute(
        select(Task)
        .where(Task.id == task_id)
        .options(selectinload(Task.tags), selectinload(Task.sub_assignees))
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="タスクが見つかりません")

    old_due = task.due_date
    task.start_date = body.new_start_date
    task.due_date = body.new_due_date

    dependent_tasks: list[Task] = []
    if old_due and body.new_due_date and old_due != body.new_due_date:
        delta = timedelta(days=(body.new_due_date - old_due).days)
        dependent_tasks = await _cascade_reschedule(db, task_id, delta)

    await db.commit()
    await db.refresh(task, ["tags", "sub_assignees"])
    for t in dependent_tasks:
        await db.refresh(t, ["tags", "sub_assignees"])

    return RescheduleResponse(
        updated_tasks=[_task_to_response(t) for t in [task, *dependent_tasks]]
    )
