from __future__ import annotations
import json
from dataclasses import dataclass
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

    def get_users_dev(self) -> list[UserInfo]:
        """DEV_MODE 専用: 認証なしで /api/v1/dev/users からユーザー一覧を取得する。"""
        resp = httpx.get(
            f"{self._base}/api/v1/dev/users",
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

    def get_users(self) -> list[UserInfo]:
        resp = httpx.get(
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
        resp = httpx.get(
            f"{self._base}/api/v1/projects",
            params={"scope": "all"},
            headers=self._headers,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data if isinstance(data, list) else data.get("items", [])
        return [ProjectInfo(p["id"], p["name"]) for p in items]

    def create_task(self, payload: dict) -> dict:
        import logging
        logging.debug("create_task payload: %s", payload)
        resp = httpx.post(
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
