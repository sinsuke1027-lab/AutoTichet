from typing import Any

from src.models.task import ExtractedTask


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
