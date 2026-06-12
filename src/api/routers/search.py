import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import CurrentUser
from src.api.routers.dashboard import _scope_condition
from src.db.engine import get_db
from src.db.models import Project, Task, TaskComment
from src.models.task_web import SearchResponse, SearchResultItem

router = APIRouter(prefix="/api/v1/search", tags=["search"])

DbDep = Annotated[AsyncSession, Depends(get_db)]


def _make_snippet(text: str, keyword: str, context: int = 50) -> str:
    lower = text.lower()
    idx = lower.find(keyword.lower())
    if idx == -1:
        return text[: context * 2]
    start = max(0, idx - context)
    end = min(len(text), idx + len(keyword) + context)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return prefix + text[start:end] + suffix


@router.get("", response_model=SearchResponse)
async def search(
    q: str,
    db: DbDep,
    current_user: CurrentUser,
    limit: int = Query(default=20, le=50),
) -> SearchResponse:
    if len(q) < 2:
        raise HTTPException(status_code=422, detail="検索キーワードは2文字以上で入力してください")

    # Escape LIKE wildcards
    escaped_q = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    like = f"%{escaped_q}%"

    scope = await _scope_condition(db, current_user)

    # タスク検索（title + description）
    task_q = (
        select(Task, Project.name)
        .join(Project, Task.project_id == Project.id)
        .where(
            Task.title.ilike(like, escape="\\") | Task.description.ilike(like, escape="\\"),
        )
        .limit(limit * 2)
    )
    if scope is not None:
        task_q = task_q.where(scope)
    task_rows = (await db.execute(task_q)).all()

    # コメント検索
    comment_q = (
        select(TaskComment, Task, Project.name)
        .join(Task, TaskComment.task_id == Task.id)
        .join(Project, Task.project_id == Project.id)
        .where(
            TaskComment.content.ilike(like, escape="\\"),
        )
        .limit(limit * 2)
    )
    if scope is not None:
        comment_q = comment_q.where(scope)
    comment_rows = (await db.execute(comment_q)).all()

    # task_id 単位で重複排除（title > description > comment）
    task_items: dict[uuid.UUID, SearchResultItem] = {}
    for task, project_name in task_rows:
        if task.id in task_items:
            continue
        match_type = "title" if q.lower() in (task.title or "").lower() else "description"
        text = task.title if match_type == "title" else (task.description or task.title)
        task_items[task.id] = SearchResultItem(
            task_id=task.id,
            project_id=task.project_id,
            project_name=project_name,
            title=task.title,
            snippet=_make_snippet(text, q),
            match_type=match_type,
        )

    comment_items: list[SearchResultItem] = []
    comment_seen: set[uuid.UUID] = set()
    for comment, task, project_name in comment_rows:
        if task.id in task_items or task.id in comment_seen:
            continue
        comment_seen.add(task.id)
        comment_items.append(
            SearchResultItem(
                task_id=task.id,
                project_id=task.project_id,
                project_name=project_name,
                title=task.title,
                snippet=_make_snippet(comment.content, q),
                match_type="comment",
            )
        )

    # タスク一致を優先しつつ、コメント一致が埋もれないよう limit の一部を確保する（issue #41）
    task_list = list(task_items.values())
    comment_quota = min(len(comment_items), max(1, limit // 3)) if comment_items else 0
    task_quota = limit - comment_quota
    items = (task_list[:task_quota] + comment_items[:comment_quota])[:limit]
    return SearchResponse(items=items, total=len(items))
