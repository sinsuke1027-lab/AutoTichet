from typing import Any

import httpx

from src.connectors.graph_api import GraphAPIClient
from src.models.task import ExtractedTask

_PRIORITY_MAP = {"high": 1, "medium": 5, "low": 9}


class PlannerConnector:
    """Microsoft Planner タスク起票コネクター（Graph API経由）"""

    BASE_URL = "https://graph.microsoft.com/v1.0"

    def __init__(self, graph_client: GraphAPIClient) -> None:
        self._graph = graph_client

    async def create_task(self, task: ExtractedTask, plan_id: str) -> str:
        """Planner にタスクを起票し、作成されたタスクIDを返す"""
        body: dict[str, Any] = {
            "planId": plan_id,
            "title": task.title,
            "priority": _PRIORITY_MAP[task.priority],
        }

        if task.assignee_user_id:
            body["assignments"] = {
                task.assignee_user_id: {
                    "@odata.type": "microsoft.graph.plannerAssignment",
                    "orderHint": " !",
                }
            }

        if task.deadline:
            body["dueDateTime"] = f"{task.deadline.isoformat()}T00:00:00Z"

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/planner/tasks",
                headers=self._graph._headers(),
                json=body,
            )
            resp.raise_for_status()
            return str(resp.json()["id"])

    async def get_task(self, task_id: str) -> dict[str, Any]:
        """Planner タスクの詳細を取得する"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/planner/tasks/{task_id}",
                headers=self._graph._headers(),
            )
            resp.raise_for_status()
            return dict(resp.json())

    async def update_task(self, task_id: str, etag: str, updates: dict[str, Any]) -> None:
        """Planner タスクを更新する（ETag必須）"""
        async with httpx.AsyncClient() as client:
            resp = await client.patch(
                f"{self.BASE_URL}/planner/tasks/{task_id}",
                headers={**self._graph._headers(), "If-Match": etag},
                json=updates,
            )
            resp.raise_for_status()
