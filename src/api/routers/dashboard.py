from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import CurrentUser
from src.db.engine import get_db
from src.db.models import Task, TaskWorkHour, UserProfile
from src.models.task_web import DashboardSummary, WorkloadItem

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])
DbDep = Annotated[AsyncSession, Depends(get_db)]


@router.get("/summary", response_model=DashboardSummary)
async def get_summary(db: DbDep, current_user: CurrentUser) -> DashboardSummary:
    today = date.today()
    result = await db.execute(select(Task.status, func.count()).group_by(Task.status))
    counts = {row[0]: row[1] for row in result.all()}
    total = sum(counts.values())
    not_started = counts.get("not_started", 0)
    in_progress = counts.get("in_progress", 0)
    completed = counts.get("completed", 0)
    overdue_result = await db.execute(
        select(func.count(Task.id)).where(
            Task.due_date < today,
            Task.status.notin_(["completed", "cancelled"]),
        )
    )
    overdue = overdue_result.scalar_one()
    completion_rate = (completed / total * 100) if total > 0 else 0.0
    return DashboardSummary(
        total_tasks=total,
        not_started=not_started,
        in_progress=in_progress,
        completed=completed,
        overdue=overdue,
        completion_rate=round(completion_rate, 1),
    )


@router.get("/today", response_model=list[dict])
async def get_today_tasks(db: DbDep, current_user: CurrentUser) -> list[dict]:
    today = date.today()
    result = await db.execute(
        select(Task)
        .where(
            Task.due_date == today,
            Task.status.notin_(["completed", "cancelled"]),
        )
        .order_by(Task.priority.desc())
    )
    tasks = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "title": t.title,
            "status": t.status,
            "priority": t.priority,
            "assignee_id": t.assignee_id,
        }
        for t in tasks
    ]


@router.get("/overdue", response_model=list[dict])
async def get_overdue_tasks(db: DbDep, current_user: CurrentUser) -> list[dict]:
    today = date.today()
    result = await db.execute(
        select(Task)
        .where(
            Task.due_date < today,
            Task.status.notin_(["completed", "cancelled"]),
        )
        .order_by(Task.due_date.asc())
        .limit(50)
    )
    tasks = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "title": t.title,
            "status": t.status,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "assignee_id": t.assignee_id,
        }
        for t in tasks
    ]


@router.get("/workload", response_model=list[WorkloadItem])
async def get_workload(db: DbDep, current_user: CurrentUser) -> list[WorkloadItem]:
    today = date.today()
    next_week = today + timedelta(days=7)
    wh_result = await db.execute(
        select(TaskWorkHour.user_id, func.sum(TaskWorkHour.estimated_hours))
        .join(Task, Task.id == TaskWorkHour.task_id)
        .where(
            Task.due_date >= today,
            Task.due_date <= next_week,
            Task.status.notin_(["completed", "cancelled"]),
        )
        .group_by(TaskWorkHour.user_id)
    )
    user_hours = {row[0]: row[1] or 0.0 for row in wh_result.all()}

    profiles_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id.in_(list(user_hours.keys())))
    )
    profiles = {p.user_id: p for p in profiles_result.scalars().all()}

    items = []
    for user_id, hours in user_hours.items():
        profile = profiles.get(user_id)
        capacity = (profile.capacity_hours_per_day * 5) if profile else 40.0
        display_name = profile.display_name if profile else user_id
        items.append(
            WorkloadItem(
                user_id=user_id,
                display_name=display_name,
                estimated_hours=hours,
                capacity_hours=capacity,
                overload=hours > capacity,
            )
        )
    return items


@router.get("/completion-trend", response_model=list[dict])
async def get_completion_trend(db: DbDep, current_user: CurrentUser) -> list[dict]:
    today = date.today()
    result = []
    for i in range(7, -1, -1):
        day = today - timedelta(days=i)
        count_result = await db.execute(
            select(func.count(Task.id)).where(
                func.date(Task.updated_at) == day,
                Task.status == "completed",
            )
        )
        result.append({"date": day.isoformat(), "completed": count_result.scalar_one()})
    return result
