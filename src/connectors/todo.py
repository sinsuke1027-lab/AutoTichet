from typing import Any

import httpx

from src.connectors.graph_api import GraphAPIClient
from src.models.task import ExtractedTask

_IMPORTANCE_MAP = {"high": "high", "medium": "normal", "low": "low"}
_DEFAULT_LIST_NAME = "AutoTicket"


class TodoConnector:
    """Microsoft To Do プライベートタスク起票コネクター（Graph API経由）"""

    BASE_URL = "https://graph.microsoft.com/v1.0"

    def __init__(self, graph_client: GraphAPIClient) -> None:
        self._graph = graph_client

    async def get_or_create_list(self, user_id: str, list_name: str = _DEFAULT_LIST_NAME) -> str:
        """指定名のTo Doリストを返す。存在しなければ作成する。"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/users/{user_id}/todo/lists",
                headers=self._graph._headers(),
            )
            resp.raise_for_status()
            for lst in resp.json().get("value", []):
                if lst.get("displayName") == list_name:
                    return str(lst["id"])

            resp = await client.post(
                f"{self.BASE_URL}/users/{user_id}/todo/lists",
                headers=self._graph._headers(),
                json={"displayName": list_name},
            )
            resp.raise_for_status()
            return str(resp.json()["id"])

    async def create_task(
        self,
        task: ExtractedTask,
        user_id: str | None = None,
        todo_list_id: str | None = None,
    ) -> str:
        """To Do にプライベートタスクを起票し、作成されたタスクIDを返す"""
        uid = user_id or task.assignee_user_id or ""
        if not uid:
            raise ValueError("user_id または task.assignee_user_id が必要です")

        list_id = todo_list_id or await self.get_or_create_list(uid)

        body: dict[str, Any] = {
            "title": task.title,
            "importance": _IMPORTANCE_MAP[task.priority],
        }

        if task.deadline:
            body["dueDateTime"] = {
                "dateTime": f"{task.deadline.isoformat()}T00:00:00",
                "timeZone": "UTC",
            }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/users/{uid}/todo/lists/{list_id}/tasks",
                headers=self._graph._headers(),
                json=body,
            )
            resp.raise_for_status()
            return str(resp.json()["id"])
