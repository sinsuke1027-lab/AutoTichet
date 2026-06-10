from __future__ import annotations
from datetime import date, datetime
from widget.clients.backend_client import UserInfo, ProjectInfo

_PRIORITY_MAP = {"低": "low", "中": "medium", "高": "high", "緊急": "urgent"}

_DATE_FORMATS = [
    "%Y-%m-%d",   # 2026-06-15
    "%Y/%m/%d",   # 2026/06/15 or 2026/6/15
    "%m/%d/%Y",   # 06/15/2026
    "%m-%d-%Y",   # 06-15-2026
    "%m/%d",      # 6/15  → 今年
    "%m-%d",      # 6-15  → 今年
]


def normalize_date(s: str) -> str | None:
    s = s.strip()
    if not s:
        return None
    year = date.today().year
    for fmt in _DATE_FORMATS:
        try:
            if fmt in ("%m/%d", "%m-%d"):
                sep = fmt[2]
                d = datetime.strptime(f"{year}{sep}{s}", f"%Y{sep}{fmt}")
            else:
                d = datetime.strptime(s, fmt)
            return d.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


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
    description: str = "",
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
        "due_date": normalize_date(due_date_str),
        "assignee_id": assignee_id,
        "project_id": project_id,
        "priority": jp_to_priority(priority_jp),
        "description": description,
        "source_type": "manual",
    }
