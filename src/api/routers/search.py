import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import CurrentUser
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

    like = f"%{q}%"
    visibility_cond = or_(
        Task.visibility != "private",
        Task.assignee_id == current_user.sub,
        Task.created_by == current_user.sub,
    )

    # タスク検索（title + description）
    task_q = (
        select(Task, Project.name)
        .join(Project, Task.project_id == Project.id)
        .where(
            Task.title.ilike(like) | Task.description.ilike(like),
            visibility_cond,
        )
        .limit(limit * 2)
    )
    task_rows = (await db.execute(task_q)).all()

    # コメント検索
    comment_q = (
        select(TaskComment, Task, Project.name)
        .join(Task, TaskComment.task_id == Task.id)
        .join(Project, Task.project_id == Project.id)
        .where(
            TaskComment.content.ilike(like),
            visibility_cond,
        )
        .limit(limit * 2)
    )
    comment_rows = (await db.execute(comment_q)).all()

    # task_id 単位で重複排除（title > description > comment）
    seen: dict[uuid.UUID, SearchResultItem] = {}

    for task, project_name in task_rows:
        if task.id in seen:
            continue
        match_type = "title" if q.lower() in (task.title or "").lower() else "description"
        text = task.title if match_type == "title" else (task.description or task.title)
        seen[task.id] = SearchResultItem(
            task_id=task.id,
            project_id=task.project_id,
            project_name=project_name,
            title=task.title,
            snippet=_make_snippet(text, q),
            match_type=match_type,
        )

    for comment, task, project_name in comment_rows:
        if task.id in seen:
            continue
        seen[task.id] = SearchResultItem(
            task_id=task.id,
            project_id=task.project_id,
            project_name=project_name,
            title=task.title,
            snippet=_make_snippet(comment.content, q),
            match_type="comment",
        )

    items = list(seen.values())[:limit]
    return SearchResponse(items=items, total=len(seen))
