from __future__ import annotations
from widget.clients.backend_client import UserInfo, ProjectInfo

_PRIORITY_MAP = {"低": "low", "中": "medium", "高": "high", "緊急": "urgent"}


def jp_to_priority(jp: str) -> str:
    return _PRIORITY_MAP.get(jp, "medium")


def resolve_assignee(name: str, users: list[UserInfo]) -> str | None:
    lower = name.lower()
    for u in users:
        if lower in u.display_name.lower():
            return u.user_id
    return None


def resolve_project(name: str, projects: list[ProjectInfo]) -> str | None:
    for p in projects:
        if p.name == name:
            return p.id
    return None


def build_payload(
    title: str,
    due_date_str: str,
    assignee_display: str,
    project_name: str,
    priority_jp: str,
    users: list[UserInfo],
    projects: list[ProjectInfo],
) -> dict:
    assignee_id = (
        None
        if assignee_display in ("（なし）", "")
        else resolve_assignee(assignee_display, users)
    )
    project_id = (
        None
        if project_name in ("（なし）", "")
        else resolve_project(project_name, projects)
    )
    return {
        "title": title,
        "due_date": due_date_str.strip() or None,
        "assignee_id": assignee_id,
        "project_id": project_id,
        "priority": jp_to_priority(priority_jp),
        "source_type": "manual",
    }
