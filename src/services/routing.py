from typing import Any

from src.db.engine import AsyncSessionLocal
from src.db.models import Task as TaskORM
from src.models.task import ExtractedTask


async def _save_tasks_to_postgres(
    tasks: list[dict[str, Any]],
    source_type: str,
    source_id: str,
    confidence_score: float,
    route: str,
) -> list[str]:
    """タスクを PostgreSQL に保存して保存済み ID のリストを返す

    Args:
        tasks: タスク辞書のリスト（title, description, assignee_id, due_date, visibility を含む）
        source_type: ソースの種別（email / meeting / chat など）
        source_id: ソースの識別子
        confidence_score: 信頼スコア
        route: ルーティング区分（auto_create など）

    Returns:
        保存されたタスクの UUID 文字列リスト
    """
    saved_ids: list[str] = []
    async with AsyncSessionLocal() as session:
        for task_dict in tasks:
            task = TaskORM(
                title=task_dict.get("title", "（タイトルなし）"),
                description=task_dict.get("description"),
                assignee_id=task_dict.get("assignee_id"),
                due_date=task_dict.get("due_date"),
                visibility=task_dict.get("visibility", "team"),
                source_type=source_type,
                source_id=source_id,
                confidence_score=confidence_score,
                route=route,
                created_by="system",
            )
            session.add(task)
            await session.flush()
            saved_ids.append(str(task.id))
        await session.commit()
    return saved_ids


async def route_task(
    task: ExtractedTask,
    todo_connector: Any,
    planner_connector: Any,
    company_plan_id: str,
    dept_plan_map: dict[str, str],
) -> None:
    """visibility に応じてタスクを起票先へルーティング

    Args:
        task: 抽出されたタスク
        todo_connector: Microsoft To Do コネクタ
        planner_connector: Microsoft Planner コネクタ
        company_plan_id: 全社プランのID
        dept_plan_map: 部署ID → プランID マッピング
    """
    match task.visibility:
        case "private":
            await todo_connector.create_task(task=task)
        case "team":
            plan_id = dept_plan_map.get(task.department_id or "", company_plan_id)
            await planner_connector.create_task(task=task, plan_id=plan_id)
        case "all":
            await planner_connector.create_task(task=task, plan_id=company_plan_id)
