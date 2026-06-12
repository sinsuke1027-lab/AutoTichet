from datetime import UTC, date, datetime, timedelta
from datetime import time as time_type
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import array as pg_array
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import ROLE_HIERARCHY, CurrentUser
from src.db.engine import get_db
from src.db.models import Task, TaskWorkHour, UserProfile
from src.models.task_web import (
    DailyWorkloadItem,
    DashboardSummary,
    OverdueTaskItem,
    StaleTaskItem,
    TaskStatus,
    TodayTaskItem,
    TrendPoint,
    WeeklyWorkSummary,
    WorkloadItem,
)

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])
DbDep = Annotated[AsyncSession, Depends(get_db)]


async def _scope_condition(db: AsyncSession, current_user: CurrentUser):  # type: ignore[return]
    """ロールに応じたタスク絞り込み条件を返す。manager/admin は None（全件）。"""
    user_role = max((ROLE_HIERARCHY.get(r, 0) for r in current_user.roles), default=0)
    if user_role >= ROLE_HIERARCHY["manager"]:
        return None
    if user_role >= ROLE_HIERARCHY["leader"] and current_user.department_tags:
        dept_result = await db.execute(
            select(UserProfile.user_id).where(
                UserProfile.department_tags.op("?|")(pg_array(current_user.department_tags))
            )
        )
        dept_user_ids = list(dept_result.scalars().all())
        return or_(Task.assignee_id.in_(dept_user_ids), Task.visibility == "all")
    return or_(Task.assignee_id == current_user.sub, Task.visibility == "all")


@router.get("/summary", response_model=DashboardSummary)
async def get_summary(db: DbDep, current_user: CurrentUser) -> DashboardSummary:
    today = date.today()
    scope = await _scope_condition(db, current_user)

    count_query = select(Task.status, func.count()).group_by(Task.status)
    if scope is not None:
        count_query = count_query.where(scope)
    result = await db.execute(count_query)
    counts = {row[0]: row[1] for row in result.all()}
    total = sum(counts.values())
    not_started = counts.get("not_started", 0)
    in_progress = counts.get("in_progress", 0)
    completed = counts.get("completed", 0)

    overdue_query = select(func.count(Task.id)).where(
        Task.due_date < today,
        Task.status.notin_(["completed", "cancelled"]),
    )
    if scope is not None:
        overdue_query = overdue_query.where(scope)
    overdue_result = await db.execute(overdue_query)
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
            Task.assignee_id == current_user.sub,
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
    scope = await _scope_condition(db, current_user)
    overdue_query = (
        select(Task)
        .where(
            Task.due_date < today,
            Task.status.notin_(["completed", "cancelled"]),
        )
        .order_by(Task.due_date.asc())
        .limit(50)
    )
    if scope is not None:
        overdue_query = overdue_query.where(scope)
    result = await db.execute(overdue_query)
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

    user_role = max((ROLE_HIERARCHY.get(r, 0) for r in current_user.roles), default=0)

    # ロールに応じて閲覧対象ユーザーのプロファイルを取得
    if user_role >= ROLE_HIERARCHY["manager"]:
        prof_result = await db.execute(select(UserProfile).order_by(UserProfile.display_name))
    elif user_role >= ROLE_HIERARCHY["leader"] and current_user.department_tags:
        prof_result = await db.execute(
            select(UserProfile)
            .where(UserProfile.department_tags.op("?|")(pg_array(current_user.department_tags)))
            .order_by(UserProfile.display_name)
        )
    else:
        # member: 自分のみ
        prof_result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == current_user.sub)
        )

    profiles = {p.user_id: p for p in prof_result.scalars().all()}
    if not profiles:
        return []

    wh_result = await db.execute(
        select(TaskWorkHour.user_id, func.sum(TaskWorkHour.estimated_hours))
        .join(Task, Task.id == TaskWorkHour.task_id)
        .where(
            Task.due_date >= today,
            Task.due_date <= next_week,
            Task.status.notin_(["completed", "cancelled"]),
            TaskWorkHour.user_id.in_(list(profiles.keys())),
        )
        .group_by(TaskWorkHour.user_id)
    )
    user_hours = {row[0]: float(row[1] or 0.0) for row in wh_result.all()}

    # 工数未登録のメンバーも 0h で含める（チーム全員が見えるように）
    return [
        WorkloadItem(
            user_id=uid,
            display_name=p.display_name,
            estimated_hours=user_hours.get(uid, 0.0),
            capacity_hours=p.capacity_hours_per_day * 5,
            overload=user_hours.get(uid, 0.0) > p.capacity_hours_per_day * 5,
        )
        for uid, p in profiles.items()
    ]


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


@router.get("/daily-workload", response_model=list[DailyWorkloadItem])
async def get_daily_workload(db: DbDep, current_user: CurrentUser) -> list[DailyWorkloadItem]:
    today = date.today()
    end_date = today + timedelta(days=6)

    user_role = max(
        (ROLE_HIERARCHY.get(r, 0) for r in current_user.roles),
        default=0,
    )

    # estimated_hours: task ごとに最大値を採用（複数エントリ対策）
    wh_sub = (
        select(
            TaskWorkHour.task_id,
            func.max(TaskWorkHour.estimated_hours).label("estimated_hours"),
        )
        .group_by(TaskWorkHour.task_id)
        .subquery()
    )

    base_query = (
        select(
            Task.due_date.label("task_date"),
            func.sum(func.coalesce(wh_sub.c.estimated_hours, 1.0)).label("total_hours"),
            func.count(Task.id).label("task_count"),
        )
        .outerjoin(wh_sub, wh_sub.c.task_id == Task.id)
        .where(
            Task.due_date >= today,
            Task.due_date <= end_date,
            Task.status.notin_(["completed", "cancelled"]),
            Task.due_date.isnot(None),
        )
    )

    capacity_hours: float = 8.0

    if user_role < ROLE_HIERARCHY["manager"]:
        if user_role >= ROLE_HIERARCHY["leader"] and current_user.department_tags:
            dept_result = await db.execute(
                select(UserProfile.user_id).where(
                    UserProfile.department_tags.op("?|")(pg_array(current_user.department_tags))
                )
            )
            dept_user_ids = list(dept_result.scalars().all())
            base_query = base_query.where(Task.assignee_id.in_(dept_user_ids))
            cap_result = await db.execute(
                select(func.avg(UserProfile.capacity_hours_per_day)).where(
                    UserProfile.user_id.in_(dept_user_ids)
                )
            )
            capacity_hours = float(cap_result.scalar_one_or_none() or 8.0)
        else:
            # leader without dept_tags: own tasks only (workload — no visibility filter)
            base_query = base_query.where(Task.assignee_id == current_user.sub)
            cap_result = await db.execute(
                select(UserProfile.capacity_hours_per_day).where(
                    UserProfile.user_id == current_user.sub
                )
            )
            capacity_hours = float(cap_result.scalar_one_or_none() or 8.0)
    else:
        cap_result = await db.execute(select(func.avg(UserProfile.capacity_hours_per_day)))
        capacity_hours = float(cap_result.scalar_one() or 8.0)

    result = await db.execute(base_query.group_by(Task.due_date))
    rows: dict[str, tuple[float, int]] = {
        str(row[0]): (float(row[1] or 0.0), int(row[2] or 0)) for row in result.all()
    }

    return [
        DailyWorkloadItem(
            date=(today + timedelta(days=i)).isoformat(),
            total_hours=round(rows.get((today + timedelta(days=i)).isoformat(), (0.0, 0))[0], 1),
            capacity_hours=round(capacity_hours, 1),
            overload=round(rows.get((today + timedelta(days=i)).isoformat(), (0.0, 0))[0], 1)
            > round(capacity_hours, 1),
            task_count=rows.get((today + timedelta(days=i)).isoformat(), (0.0, 0))[1],
        )
        for i in range(7)
    ]


def _ensure_aware(dt: datetime) -> datetime:
    """naive な datetime を UTC aware に正規化する（SQLite 対策・issue #19）

    SQLite は ``DateTime(timezone=True)`` 列でも timezone 情報を落として naive な
    値を返すことがあり、aware な ``datetime.now(UTC)`` との減算で TypeError になる。
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


@router.get("/stale-tasks", response_model=list[StaleTaskItem])
async def get_stale_tasks(db: DbDep, current_user: CurrentUser) -> list[StaleTaskItem]:
    """14日以上更新のないアクティブタスク一覧（ロールスコープ適用）"""
    cutoff = datetime.now(UTC) - timedelta(days=14)
    scope = await _scope_condition(db, current_user)
    query = (
        select(Task)
        .where(
            Task.status.notin_(["completed", "cancelled"]),
            Task.updated_at < cutoff,
        )
        .order_by(Task.updated_at.asc())
        .limit(10)
    )
    if scope is not None:
        query = query.where(scope)
    result = await db.execute(query)
    tasks = result.scalars().all()
    now = datetime.now(UTC)
    return [
        StaleTaskItem(
            id=t.id,
            title=t.title,
            assignee_id=t.assignee_id,
            due_date=t.due_date,
            updated_at=t.updated_at,
            days_stale=(now - _ensure_aware(t.updated_at)).days,
        )
        for t in tasks
    ]


@router.get("/my-weekly-summary", response_model=list[WeeklyWorkSummary])
async def get_my_weekly_summary(db: DbDep, current_user: CurrentUser) -> list[WeeklyWorkSummary]:
    today = date.today()
    this_monday = today - timedelta(days=today.weekday())

    results: list[WeeklyWorkSummary] = []
    for i in range(3, -1, -1):  # 3週前 → 今週（古い順）
        week_start = this_monday - timedelta(weeks=i)
        week_end = week_start + timedelta(days=6)

        # タスク集計
        task_result = await db.execute(
            select(Task.status, func.count(Task.id))
            .where(
                Task.assignee_id == current_user.sub,
                Task.due_date >= week_start,
                Task.due_date <= week_end,
                Task.due_date.isnot(None),
            )
            .group_by(Task.status)
        )
        status_counts: dict[str, int] = {row[0]: row[1] for row in task_result.all()}
        task_count = sum(status_counts.values())
        completed_count = status_counts.get("completed", 0)

        # 工数集計
        wh_result = await db.execute(
            select(
                func.coalesce(func.sum(TaskWorkHour.estimated_hours), 0.0),
                func.coalesce(func.sum(TaskWorkHour.actual_hours), 0.0),
            )
            .join(Task, Task.id == TaskWorkHour.task_id)
            .where(
                TaskWorkHour.user_id == current_user.sub,
                Task.due_date >= week_start,
                Task.due_date <= week_end,
                Task.due_date.isnot(None),
            )
        )
        planned_hours, actual_hours = wh_result.one()

        # 期限超過（最新週のみ）
        overdue_count = 0
        if i == 0:
            overdue_result = await db.execute(
                select(func.count(Task.id)).where(
                    Task.assignee_id == current_user.sub,
                    Task.due_date < today,
                    Task.status.notin_(["completed", "cancelled"]),
                )
            )
            overdue_count = overdue_result.scalar_one()

        results.append(
            WeeklyWorkSummary(
                week_start=week_start,
                planned_hours=float(planned_hours),
                actual_hours=float(actual_hours),
                task_count=task_count,
                completed_count=completed_count,
                overdue_count=overdue_count,
            )
        )

    return results
