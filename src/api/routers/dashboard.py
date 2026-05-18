from datetime import date, datetime, timedelta
from datetime import time as time_type
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import CurrentUser
from src.db.engine import get_db
from src.db.models import Task, TaskWorkHour, UserProfile
from src.models.task_web import (
    DashboardSummary,
    OverdueTaskItem,
    TaskStatus,
    TodayTaskItem,
    TrendPoint,
    WorkloadItem,
)

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


@router.get("/today", response_model=list[TodayTaskItem])
async def get_today_tasks(db: DbDep, current_user: CurrentUser) -> list[TodayTaskItem]:
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
        TodayTaskItem(
            id=t.id,
            title=t.title,
            status=t.status,
            priority=t.priority,
            assignee_id=t.assignee_id,
        )
        for t in tasks
    ]


@router.get("/overdue", response_model=list[OverdueTaskItem])
async def get_overdue_tasks(db: DbDep, current_user: CurrentUser) -> list[OverdueTaskItem]:
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
        OverdueTaskItem(
            id=t.id,
            title=t.title,
            status=t.status,
            due_date=t.due_date.isoformat() if t.due_date else None,
            assignee_id=t.assignee_id,
        )
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


@router.get("/completion-trend", response_model=list[TrendPoint])
async def get_completion_trend(db: DbDep, current_user: CurrentUser) -> list[TrendPoint]:
    today = date.today()
    start = today - timedelta(days=7)
    start_dt = datetime.combine(start, time_type.min)
    end_dt = datetime.combine(today + timedelta(days=1), time_type.min)

    rows_result = await db.execute(
        select(
            func.date(Task.updated_at).label("day"),
            func.count(Task.id).label("completed"),
        )
        .where(
            Task.updated_at >= start_dt,
            Task.updated_at < end_dt,
            Task.status == TaskStatus.COMPLETED.value,
        )
        .group_by(func.date(Task.updated_at))
    )
    counts_by_day: dict[str, int] = {str(row[0]): row[1] for row in rows_result.all()}
    return [
        TrendPoint(
            date=(today - timedelta(days=i)).isoformat(),
            completed=counts_by_day.get((today - timedelta(days=i)).isoformat(), 0),
        )
        for i in range(7, -1, -1)
    ]
