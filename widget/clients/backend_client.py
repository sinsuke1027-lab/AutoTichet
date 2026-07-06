from __future__ import annotations
import json
import logging
from dataclasses import dataclass
from datetime import date, timedelta
import httpx


@dataclass(eq=True)
class UserInfo:
    user_id: str
    display_name: str
    role: str = "member"
    email: str = ""


@dataclass(eq=True)
class ProjectInfo:
    id: str
    name: str


@dataclass
class TaskItem:
    task_id: str
    title: str
    status: str
    due_date: str | None
    priority: str | None
    assignee_name: str | None
    start_date: str | None = None


def _task_item_from_dict(d: dict) -> TaskItem:
    due = d.get("due_date")
    start = d.get("start_date")
    return TaskItem(
        task_id=str(d["id"]),
        title=d["title"],
        status=d.get("status", "not_started"),
        due_date=str(due) if due else None,
        priority=d.get("priority"),
        assignee_name=d.get("assignee_name"),
        start_date=str(start) if start else None,
    )


class BackendClient:
    def __init__(self, backend_url: str, user: UserInfo) -> None:
        self._base = backend_url.rstrip("/")
        dev_header = json.dumps({
            "userId": user.user_id,
            "displayName": user.display_name,
            "email": user.email or f"{user.user_id}@dev.example.com",
            "role": user.role,
            "departmentTags": [],
        })
        self._headers = {"X-Dev-User": dev_header, "Content-Type": "application/json"}
        # 呼び出しごとにTCP+TLSハンドシェイクをやり直さないよう、Clientを使い回す
        self._client = httpx.Client()

    def close(self) -> None:
        self._client.close()

    def get_users_dev(self) -> list[UserInfo]:
        """DEV_MODE 専用: 認証なしで /api/v1/dev/users からユーザー一覧を取得する。"""
        resp = self._client.get(
            f"{self._base}/api/v1/dev/users",
            timeout=90,  # HuggingFace Spaces のスリープ復帰に最大60秒かかる
        )
        resp.raise_for_status()
        return [
            UserInfo(
                user_id=u["user_id"],
                display_name=u["display_name"],
                role=u.get("role", "member"),
                email=u.get("email") or "",
            )
            for u in resp.json()
        ]

    def get_users(self) -> list[UserInfo]:
        resp = self._client.get(
            f"{self._base}/api/v1/users",
            headers=self._headers,
            timeout=10,
        )
        resp.raise_for_status()
        return [
            UserInfo(
                user_id=u["user_id"],
                display_name=u["display_name"],
                role=u.get("role", "member"),
                email=u.get("email") or "",
            )
            for u in resp.json()
        ]

    def get_projects(self) -> list[ProjectInfo]:
        resp = self._client.get(
            f"{self._base}/api/v1/projects",
            params={"scope": "all"},
            headers=self._headers,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data if isinstance(data, list) else data.get("items", [])
        return [ProjectInfo(p["id"], p["name"]) for p in items]

    def get_today_tasks(self) -> list[TaskItem]:
        today = date.today().isoformat()
        resp = self._client.get(
            f"{self._base}/api/v1/tasks",
            params={"due_date_gte": today, "due_date_lte": today, "limit": 100},
            headers=self._headers,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data if isinstance(data, list) else data.get("items", [])
        return [_task_item_from_dict(t) for t in items]

    def get_overdue_tasks(self) -> list[TaskItem]:
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        resp = self._client.get(
            f"{self._base}/api/v1/tasks",
            params={"due_date_lte": yesterday, "limit": 100},
            headers=self._headers,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data if isinstance(data, list) else data.get("items", [])
        overdue = [
            _task_item_from_dict(t) for t in items
            if t.get("status") not in ("completed", "cancelled")
        ]
        logging.debug("get_overdue_tasks: %d items", len(overdue))
        return overdue

    def get_start_overdue_tasks(self) -> list[TaskItem]:
        """開始予定日が昨日以前で未完了のタスクを取得する。ステータス絞り込みはクライアント側で行う。"""
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        resp = self._client.get(
            f"{self._base}/api/v1/tasks",
            params={"start_date_lte": yesterday, "limit": 100},
            headers=self._headers,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data if isinstance(data, list) else data.get("items", [])
        return [
            _task_item_from_dict(t) for t in items
            if t.get("status") in ("not_started", "in_progress")
        ]

    def complete_task(self, task_id: str) -> None:
        resp = self._client.put(
            f"{self._base}/api/v1/tasks/{task_id}",
            json={"status": "completed"},
            headers=self._headers,
            timeout=15,
        )
        if not resp.is_success:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise ValueError(f"HTTP {resp.status_code}: {detail}")

    def record_work_hours(
        self,
        task_id: str,
        estimated_hours: float | None = None,
        actual_hours: float | None = None,
    ) -> None:
        payload: dict = {}
        if estimated_hours is not None:
            payload["estimated_hours"] = estimated_hours
        if actual_hours is not None:
            payload["actual_hours"] = actual_hours
        if not payload:
            return
        resp = self._client.post(
            f"{self._base}/api/v1/tasks/{task_id}/work-hours",
            json=payload,
            headers=self._headers,
            timeout=15,
        )
        if not resp.is_success:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise ValueError(f"HTTP {resp.status_code}: {detail}")

    def create_task(self, payload: dict) -> dict:
        logging.debug("create_task payload: %s", payload)
        resp = self._client.post(
            f"{self._base}/api/v1/tasks",
            json=payload,
            headers=self._headers,
            timeout=15,
        )
        if not resp.is_success:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise ValueError(f"HTTP {resp.status_code}: {detail}")
        return resp.json()
