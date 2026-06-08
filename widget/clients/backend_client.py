from __future__ import annotations
from dataclasses import dataclass
import httpx


@dataclass(eq=True)
class UserInfo:
    user_id: str
    display_name: str


@dataclass(eq=True)
class ProjectInfo:
    id: str
    name: str


class BackendClient:
    def __init__(self, backend_url: str, user_id: str) -> None:
        self._base = backend_url.rstrip("/")
        self._headers = {
            "X-Dev-User": user_id,
            "Content-Type": "application/json",
        }

    def get_users(self) -> list[UserInfo]:
        resp = httpx.get(
            f"{self._base}/api/v1/users",
            headers=self._headers,
            timeout=10,
        )
        resp.raise_for_status()
        return [UserInfo(u["user_id"], u["display_name"]) for u in resp.json()]

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
        resp = httpx.post(
            f"{self._base}/api/v1/tasks",
            json=payload,
            headers=self._headers,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
