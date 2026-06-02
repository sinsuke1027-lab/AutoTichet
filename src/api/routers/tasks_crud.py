import csv
import io
import logging
import re
import uuid
from collections import deque
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import distinct, func, or_, select
from sqlalchemy.dialects.postgresql import array as pg_array
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.auth import ROLE_HIERARCHY, CurrentUser
from src.db.engine import get_db
from src.db.models import (
    Project,
    Task,
    TaskAssignee,
    TaskDependency,
    TaskTag,
    TaskWorkHour,
    UserProfile,
)
from src.models.config import Settings, get_settings
from src.models.task import ExtractedTask
from src.models.task_web import (
    ClarifyIssue,
    ClarifyRequirementsResponse,
    GenerateHandoverResponse,
    GenerateSubtasksResponse,
    HandoverRequest,
    HourEstimate,
    RescheduleRequest,
    RescheduleResponse,
    SimilarTaskResponse,
    TaskCreate,
    TaskListResponse,
    TaskResponse,
    TaskStatus,
    TaskUpdate,
)
from src.providers.gemini import GeminiProvider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])

DbDep = Annotated[AsyncSession, Depends(get_db)]

_CSV_HEADERS = [
    "ID",
    "タイトル",
    "ステータス",
    "優先度",
    "担当者",
    "サブ担当者",
    "開始日",
    "期限日",
    "完了日時",
    "プロジェクト名",
    "セクション名",
    "タグ",
    "説明",
    "見積工数(h)",
    "実績工数(h)",
    "リスクレベル",
    "信頼スコア",
    "ソース種別",
    "作成日時",
    "更新日時",
]

MAX_EXPORT_ROWS = 10_000


def _compute_risk_level(task: Task) -> str | None:
    """due_date・status・work_hours から遅延リスクレベルを返す純粋関数。"""
    if task.status in ("completed", "cancelled") or task.due_date is None:
        return None

    today = date.today()
    days_until_due = (task.due_date - today).days
    score = 0

    if days_until_due < 0:
        score += 60
    elif days_until_due <= 3:
        score += 20
    elif days_until_due <= 7:
        score += 10

    if task.status == "not_started" and 0 <= days_until_due <= 14:
        score += 20

    work_hours: list[TaskWorkHour] = task.work_hours or []
    estimated_total = sum(wh.estimated_hours for wh in work_hours if wh.estimated_hours)
    actual_total = sum(wh.actual_hours for wh in work_hours if wh.actual_hours)
    if estimated_total > 0 and actual_total > estimated_total * 1.2:
        score += 15

    if task.status == "in_progress" and not any(
        wh.actual_hours for wh in work_hours if wh.actual_hours
    ):
        score += 10

    if score >= 60:
        return "high"
    if score >= 30:
        return "medium"
    return None


def _task_to_response(task: Task) -> TaskResponse:
    tags = [t.tag for t in task.tags] if task.tags else []
    sub_assignees = [a.user_id for a in task.sub_assignees] if task.sub_assignees else []
    subtasks = task.subtasks if task.subtasks is not None else []
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
        subtask_count=len(subtasks),
        subtask_done_count=sum(1 for s in subtasks if s.status == "completed"),
        risk_level=_compute_risk_level(task),
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
    my_tasks_only: bool = Query(default=False),
    include_archived_projects: bool = Query(default=False),
) -> TaskListResponse:
    query = select(Task).options(
        selectinload(Task.tags),
        selectinload(Task.sub_assignees),
        selectinload(Task.subtasks),
        selectinload(Task.work_hours),
    )
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

    # F-07: 個人 ToDo フィルタ（ロールフィルタより先に適用）
    if my_tasks_only:
        query = query.where(
            Task.assignee_id == current_user.sub,
            Task.visibility == "private",
        )

    # ロールベース閲覧制御（適用順序: 通常フィルタ → my_tasks_only → ロールフィルタ）
    # my_tasks_only=True のときは既に visibility=="private" & assignee_id 絞り込み済みのためスキップ
    user_role = max(
        (ROLE_HIERARCHY.get(r, 0) for r in current_user.roles),
        default=0,
    )
    if not my_tasks_only and user_role < ROLE_HIERARCHY["manager"]:
        if user_role >= ROLE_HIERARCHY["leader"]:
            if current_user.department_tags:
                dept_result = await db.execute(
                    select(UserProfile.user_id).where(
                        UserProfile.department_tags.op("?|")(pg_array(current_user.department_tags))
                    )
                )
                dept_user_ids = list(dept_result.scalars().all())
                query = query.where(
                    or_(
                        Task.assignee_id.in_(dept_user_ids),
                        Task.visibility == "all",
                    )
                )
            else:
                query = query.where(Task.visibility == "all")
        else:
            # member: 自分のタスク + all
            query = query.where(
                or_(
                    Task.assignee_id == current_user.sub,
                    Task.visibility == "all",
                )
            )
    # manager / admin はフィルタなし（全件）

    # アーカイブ済みプロジェクトのタスクを除外（project_id=None の個人 ToDo は対象外）
    if not include_archived_projects:
        query = query.outerjoin(Project, Task.project_id == Project.id).where(
            or_(Task.project_id.is_(None), Project.status != "archived")
        )

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
    # 個人タスク（private）は担当者未指定の場合、作成者を担当者に設定する
    # （閲覧フィルター: assignee_id==me OR visibility==all に合致させるため）
    if data.get("visibility") == "private" and not data.get("assignee_id"):
        data["assignee_id"] = current_user.sub
    task = Task(**data)
    db.add(task)
    await db.flush()
    for tag in tags:
        db.add(TaskTag(task_id=task.id, tag=tag))
    await db.commit()
    await db.refresh(task, ["tags", "sub_assignees", "subtasks"])
    return _task_to_response(task)


@router.get("/similar", response_model=list[SimilarTaskResponse])
async def similar_tasks(
    db: DbDep,
    current_user: CurrentUser,
    q: str = Query(min_length=3),
) -> list[SimilarTaskResponse]:
    tokens = [t for t in re.split(r"[　 、。，．・\s]+", q) if t]
    if not tokens:
        return []

    conditions = [Task.title.ilike(f"%{t}%") for t in tokens]
    sim_query = select(Task).where(or_(*conditions))

    # ロールベース認可フィルタ（list_tasks と同一ロジック）
    sim_user_role = max(
        (ROLE_HIERARCHY.get(r, 0) for r in current_user.roles),
        default=0,
    )
    if sim_user_role < ROLE_HIERARCHY["manager"]:
        if sim_user_role >= ROLE_HIERARCHY["leader"]:
            if current_user.department_tags:
                dept_result = await db.execute(
                    select(UserProfile.user_id).where(
                        UserProfile.department_tags.op("?|")(pg_array(current_user.department_tags))
                    )
                )
                dept_user_ids = list(dept_result.scalars().all())
                sim_query = sim_query.where(
                    or_(
                        Task.assignee_id.in_(dept_user_ids),
                        Task.visibility == "all",
                    )
                )
            else:
                sim_query = sim_query.where(Task.visibility == "all")
        else:
            # member: 自分のタスク + all
            sim_query = sim_query.where(
                or_(
                    Task.assignee_id == current_user.sub,
                    Task.visibility == "all",
                )
            )
    # manager / admin はフィルタなし（全件）

    result = await db.execute(sim_query.limit(100))
    tasks_found = result.scalars().all()

    scored: list[tuple[float, Task]] = []
    for task in tasks_found:
        match_count = sum(1 for t in tokens if t.lower() in task.title.lower())
        score = match_count / len(tokens)
        if score >= 0.5:
            scored.append((score, task))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        SimilarTaskResponse(id=task.id, title=task.title, status=task.status, score=sc)
        for sc, task in scored[:5]
    ]


@router.get("/estimate-hours", response_model=HourEstimate)
async def estimate_hours(
    db: DbDep,
    current_user: CurrentUser,
    tags: list[str] = Query(default=[]),  # noqa: B008
) -> HourEstimate:
    if not tags:
        return HourEstimate(
            avg_actual_hours=None,
            min_actual_hours=None,
            max_actual_hours=None,
            task_count=0,
        )

    similar_ids = select(TaskTag.task_id).where(TaskTag.tag.in_(tags)).distinct()
    result = await db.execute(
        select(
            func.avg(TaskWorkHour.actual_hours).label("avg"),
            func.min(TaskWorkHour.actual_hours).label("min"),
            func.max(TaskWorkHour.actual_hours).label("max"),
            func.count(distinct(TaskWorkHour.task_id)).label("cnt"),
        )
        .join(Task, Task.id == TaskWorkHour.task_id)
        .where(
            TaskWorkHour.task_id.in_(similar_ids),
            Task.status == "completed",
            TaskWorkHour.actual_hours.is_not(None),
        )
    )
    row = result.one()
    return HourEstimate(
        avg_actual_hours=float(row.avg) if row.avg is not None else None,
        min_actual_hours=float(row.min) if row.min is not None else None,
        max_actual_hours=float(row.max) if row.max is not None else None,
        task_count=row.cnt or 0,
    )


class ExtractRequest(BaseModel):
    text: str
    source_type: str = "email"


class ExtractResponse(BaseModel):
    tasks: list[ExtractedTask]
    skipped_reason: str | None = None


@router.post("/extract", response_model=ExtractResponse)
async def extract_from_text(
    body: ExtractRequest,
    current_user: CurrentUser,
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> ExtractResponse:
    from src.services.classifier import classify_sensitivity

    sensitivity = classify_sensitivity(body.text)
    if sensitivity.label == "pattern_b":
        return ExtractResponse(tasks=[], skipped_reason="機密データ（Pattern B）")

    if not settings.gemini_api_key:
        raise HTTPException(status_code=503, detail="LLM API が設定されていません")

    from src.providers.gemini import GeminiProvider

    provider = GeminiProvider(api_key=settings.gemini_api_key, model=settings.gemini_model)
    try:
        extracted = await provider.extract_tasks(body.text, body.source_type)
    except Exception:
        logger.exception("extract_tasks failed")
        raise HTTPException(status_code=503, detail="LLM によるタスク抽出に失敗しました")
    return ExtractResponse(tasks=extracted)


@router.post("/generate-handover", response_model=GenerateHandoverResponse)
async def generate_handover(
    body: HandoverRequest,
    db: DbDep,
    current_user: CurrentUser,
) -> GenerateHandoverResponse:
    settings = get_settings()
    target_user_id = body.assignee_id or current_user.sub

    if body.assignee_id and body.assignee_id != current_user.sub:
        user_level = max((ROLE_HIERARCHY.get(r, 0) for r in current_user.roles), default=0)
        if user_level < ROLE_HIERARCHY.get("leader", 1):
            raise HTTPException(status_code=403, detail="リーダー以上の権限が必要です")

    if not settings.gemini_api_key:
        raise HTTPException(status_code=503, detail="Gemini API キーが設定されていません")

    result = await db.execute(
        select(Task)
        .where(
            Task.assignee_id == target_user_id,
            Task.status.notin_(["completed", "cancelled"]),
        )
        .options(selectinload(Task.comments))
        .order_by(Task.due_date.asc().nulls_last())
    )
    tasks = result.scalars().all()

    lines: list[str] = []
    for task in tasks:
        lines.append(f"## {task.title}")
        lines.append(f"- ステータス: {task.status}")
        lines.append(f"- 優先度: {task.priority}")
        lines.append(f"- 期限: {task.due_date or '未設定'}")
        if task.description:
            lines.append(f"- 説明: {task.description}")
        recent = sorted(task.comments, key=lambda c: c.created_at, reverse=True)[:3]
        if recent:
            lines.append("- 最近のコメント:")
            for c in recent:
                lines.append(f"  - {c.content}")
        lines.append("")
    tasks_text = "\n".join(lines)

    provider = GeminiProvider(api_key=settings.gemini_api_key, model=settings.gemini_model)
    try:
        document = await provider.generate_handover_doc(tasks_text)
    except Exception:
        logger.exception("Gemini generate_handover_doc failed")
        raise HTTPException(
            status_code=503, detail="引き継ぎ書の生成に失敗しました。しばらく後に再試行してください"
        )

    return GenerateHandoverResponse(document=document)


@router.get("/export/csv")
async def export_tasks_csv(
    db: DbDep,
    current_user: CurrentUser,
    status_filter: TaskStatus | None = Query(default=None, alias="status"),  # noqa: B008
    assignee: str | None = None,
    project_id: uuid.UUID | None = None,
    section_id: uuid.UUID | None = None,
    tag: str | None = None,
    q: str | None = None,
    due_date_gte: date | None = Query(default=None),
    due_date_lte: date | None = Query(default=None),
    assignee_ids: list[str] | None = Query(default=None),
    my_tasks_only: bool = Query(default=False),
    include_archived_projects: bool = Query(default=False),
) -> StreamingResponse:
    query = select(Task).options(
        selectinload(Task.tags),
        selectinload(Task.sub_assignees),
        selectinload(Task.work_hours),
        selectinload(Task.project),
        selectinload(Task.section),
    )
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
    if my_tasks_only:
        query = query.where(
            Task.assignee_id == current_user.sub,
            Task.visibility == "private",
        )
    user_role = max(
        (ROLE_HIERARCHY.get(r, 0) for r in current_user.roles),
        default=0,
    )
    if not my_tasks_only and user_role < ROLE_HIERARCHY["manager"]:
        if user_role >= ROLE_HIERARCHY["leader"]:
            if current_user.department_tags:
                dept_result = await db.execute(
                    select(UserProfile.user_id).where(
                        UserProfile.department_tags.op("?|")(pg_array(current_user.department_tags))
                    )
                )
                dept_user_ids = list(dept_result.scalars().all())
                query = query.where(
                    or_(
                        Task.assignee_id.in_(dept_user_ids),
                        Task.visibility == "all",
                    )
                )
            else:
                query = query.where(Task.visibility == "all")
        else:
            query = query.where(
                or_(
                    Task.assignee_id == current_user.sub,
                    Task.visibility == "all",
                )
            )
    if not include_archived_projects:
        query = query.outerjoin(Project, Task.project_id == Project.id).where(
            or_(Task.project_id.is_(None), Project.status != "archived")
        )

    result = await db.execute(
        query.order_by(Task.due_date.asc().nulls_last()).limit(MAX_EXPORT_ROWS)
    )
    tasks = result.scalars().all()

    output = io.StringIO()
    output.write("﻿")  # UTF-8 BOM（Excel 文字化け防止）
    writer = csv.writer(output)
    writer.writerow(_CSV_HEADERS)
    for task in tasks:
        work_hours: list[TaskWorkHour] = task.work_hours or []
        est_total = sum(w.estimated_hours for w in work_hours if w.estimated_hours is not None)
        act_total = sum(w.actual_hours for w in work_hours if w.actual_hours is not None)
        writer.writerow(
            [
                str(task.id),
                task.title,
                task.status,
                task.priority,
                task.assignee_id or "",
                ",".join(a.user_id for a in task.sub_assignees),
                str(task.start_date) if task.start_date else "",
                str(task.due_date) if task.due_date else "",
                task.completed_at.isoformat() if task.completed_at else "",
                task.project.name if task.project else "",
                task.section.name if task.section else "",
                ",".join(t.tag for t in task.tags),
                task.description or "",
                str(est_total) if est_total else "",
                str(act_total) if act_total else "",
                _compute_risk_level(task) or "",
                str(task.confidence_score) if task.confidence_score is not None else "",
                task.source_type or "",
                task.created_at.isoformat(),
                task.updated_at.isoformat(),
            ]
        )

    filename = f"tasks_{date.today().strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: uuid.UUID, db: DbDep, current_user: CurrentUser) -> TaskResponse:
    result = await db.execute(
        select(Task)
        .where(Task.id == task_id)
        .options(
            selectinload(Task.tags),
            selectinload(Task.sub_assignees),
            selectinload(Task.subtasks),
            selectinload(Task.work_hours),
        )
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
        .options(
            selectinload(Task.tags), selectinload(Task.sub_assignees), selectinload(Task.subtasks)
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="タスクが見つかりません")
    user_role = max((ROLE_HIERARCHY.get(r, 0) for r in current_user.roles), default=0)
    if task.assignee_id != current_user.sub and user_role < ROLE_HIERARCHY.get("manager", 2):
        raise HTTPException(status_code=403, detail="このタスクを操作する権限がありません")
    for field, value in body.model_dump(exclude_unset=True, exclude={"tags"}).items():
        setattr(task, field, value)
    if body.tags is not None:
        for existing in list(task.tags):
            await db.delete(existing)
        await db.flush()  # flush deletes before inserting new tags
        for tag in body.tags:
            db.add(TaskTag(task_id=task.id, tag=tag))
    await db.commit()
    # flush(タグ削除)でUPDATEが発行されupdated_atがexpireするため、
    # commit後に再クエリして全属性を確実にロードする
    refreshed = await db.execute(
        select(Task)
        .where(Task.id == task_id)
        .options(
            selectinload(Task.tags),
            selectinload(Task.sub_assignees),
            selectinload(Task.subtasks),
        )
    )
    return _task_to_response(refreshed.scalar_one())


@router.post(
    "/{task_id}/duplicate", response_model=TaskResponse, status_code=status.HTTP_201_CREATED
)
async def duplicate_task(task_id: uuid.UUID, db: DbDep, current_user: CurrentUser) -> TaskResponse:
    result = await db.execute(
        select(Task)
        .where(Task.id == task_id)
        .options(
            selectinload(Task.tags), selectinload(Task.sub_assignees), selectinload(Task.subtasks)
        )
    )
    original = result.scalar_one_or_none()
    if original is None:
        raise HTTPException(status_code=404, detail="タスクが見つかりません")
    user_role = max((ROLE_HIERARCHY.get(r, 0) for r in current_user.roles), default=0)
    if original.assignee_id != current_user.sub and user_role < ROLE_HIERARCHY.get("manager", 2):
        raise HTTPException(status_code=403, detail="このタスクを操作する権限がありません")

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
    await db.refresh(new_task, ["tags", "sub_assignees", "subtasks"])
    return _task_to_response(new_task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: uuid.UUID, db: DbDep, current_user: CurrentUser) -> None:
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="タスクが見つかりません")
    user_role = max((ROLE_HIERARCHY.get(r, 0) for r in current_user.roles), default=0)
    if task.assignee_id != current_user.sub and user_role < ROLE_HIERARCHY.get("manager", 2):
        raise HTTPException(status_code=403, detail="このタスクを操作する権限がありません")
    await db.delete(task)
    await db.commit()


@router.get("/{task_id}/subtasks", response_model=list[TaskResponse])
async def list_subtasks(
    task_id: uuid.UUID, db: DbDep, current_user: CurrentUser
) -> list[TaskResponse]:
    result = await db.execute(
        select(Task)
        .where(Task.parent_task_id == task_id)
        .options(
            selectinload(Task.tags), selectinload(Task.sub_assignees), selectinload(Task.subtasks)
        )
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
                .options(
                    selectinload(Task.tags),
                    selectinload(Task.sub_assignees),
                    selectinload(Task.subtasks),
                )
            )
            task = task_result.scalar_one_or_none()
            if task:
                if task.due_date:
                    if task.start_date:
                        task.start_date = task.start_date + delta
                    task.due_date = task.due_date + delta
                    updated.append(task)
                queue.append(dep.task_id)  # due_date の有無に関わらず BFS を継続
    return updated


@router.post("/{task_id}/reschedule", response_model=RescheduleResponse)
async def reschedule_task(
    task_id: uuid.UUID, body: RescheduleRequest, db: DbDep, current_user: CurrentUser
) -> RescheduleResponse:
    result = await db.execute(
        select(Task)
        .where(Task.id == task_id)
        .options(
            selectinload(Task.tags),
            selectinload(Task.sub_assignees),
            selectinload(Task.subtasks),
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="タスクが見つかりません")

    old_due = task.due_date
    if body.new_start_date is not None:
        task.start_date = body.new_start_date
    task.due_date = body.new_due_date

    dependent_tasks: list[Task] = []
    if old_due and body.new_due_date and old_due != body.new_due_date:
        delta = body.new_due_date - old_due
        dependent_tasks = await _cascade_reschedule(db, task_id, delta)

    await db.commit()

    # _cascade_reschedule の autoflush で onupdate 列(updated_at)が expire するため
    # commit 後に再クエリして全属性を確実にロードする
    refreshed_ids = [task_id] + [t.id for t in dependent_tasks]
    refreshed: list[Task] = []
    for rid in refreshed_ids:
        r = await db.execute(
            select(Task)
            .where(Task.id == rid)
            .options(
                selectinload(Task.tags),
                selectinload(Task.sub_assignees),
                selectinload(Task.subtasks),
            )
        )
        refreshed.append(r.scalar_one())

    return RescheduleResponse(updated_tasks=[_task_to_response(t) for t in refreshed])


@router.post("/{task_id}/generate-subtasks", response_model=GenerateSubtasksResponse)
async def generate_subtasks(
    task_id: uuid.UUID, db: DbDep, current_user: CurrentUser
) -> GenerateSubtasksResponse:
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="タスクが見つかりません")

    settings = get_settings()
    if not settings.gemini_api_key:
        raise HTTPException(status_code=503, detail="Gemini API キーが設定されていません")

    provider = GeminiProvider(api_key=settings.gemini_api_key, model=settings.gemini_model)
    try:
        titles = await provider.generate_subtasks(task.title, task.description)
    except Exception:
        logger.exception("Gemini generate_subtasks failed for task %s", task_id)
        raise HTTPException(
            status_code=503, detail="サブタスク生成に失敗しました。しばらく後に再試行してください"
        )
    return GenerateSubtasksResponse(suggested_titles=titles)


@router.post("/{task_id}/clarify-requirements", response_model=ClarifyRequirementsResponse)
async def clarify_requirements_endpoint(
    task_id: uuid.UUID, db: DbDep, current_user: CurrentUser
) -> ClarifyRequirementsResponse:
    """タスクの要件不足を検知して返す。

    Gemini APIキーが未設定でもルールチェック（期限・担当者）の結果を返す（503にしない）。
    generate_subtasksと異なり、部分的な成功を許容する設計。
    """
    result = await db.execute(
        select(Task).options(selectinload(Task.sub_assignees)).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="タスクが見つかりません")

    issues: list[ClarifyIssue] = []

    if task.due_date is None:
        issues.append(
            ClarifyIssue(field="due_date", message="期限が設定されていません", suggestion=None)
        )

    if not task.sub_assignees:
        issues.append(
            ClarifyIssue(field="assignees", message="担当者が設定されていません", suggestion=None)
        )

    settings = get_settings()
    if settings.gemini_api_key:
        provider = GeminiProvider(api_key=settings.gemini_api_key, model=settings.gemini_model)
        try:
            suggestion = await provider.clarify_requirements(task.title, task.description)
            if suggestion:
                issues.append(
                    ClarifyIssue(
                        field="description",
                        message="完了条件が不明確です",
                        suggestion=suggestion,
                    )
                )
        except Exception:
            logger.exception("Gemini clarify_requirements failed for task %s", task_id)

    return ClarifyRequirementsResponse(issues=issues)
