import io
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import openpyxl

_PRIORITY_MAP: dict[str, str] = {
    "最高": "urgent",
    "高": "high",
    "中": "medium",
    "低": "low",
}


@dataclass
class AsanaRow:
    task_id: str
    name: str
    section: str
    assignee_email: str
    due_date: date | None
    start_date: date | None
    completed_at: datetime | None
    is_completed: bool
    priority: str
    notes: str
    tags: list[str]
    blocked_by: list[str]
    created_at: datetime | None
    parent_task_name: str
    sub_assignee_emails: list[str] = field(default_factory=list)


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
    if not s:
        return None
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    if not s:
        return None
    for fmt in ("%Y/%m/%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def parse_asana_xlsx(xlsx_bytes: bytes) -> list[AsanaRow]:
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        return []
    headers = [str(h).strip() if h is not None else "" for h in rows[0]]

    def cell(row: tuple, col: str) -> Any:
        try:
            idx = headers.index(col)
            return row[idx]
        except ValueError:
            return None

    result: list[AsanaRow] = []
    for row in rows[1:]:
        name = str(cell(row, "Name") or "").strip()
        if not name:
            continue
        completed_at_raw = cell(row, "Completed At")
        completed_at = _parse_datetime(completed_at_raw)
        priority_raw = str(cell(row, "優先度") or "").strip()
        priority = _PRIORITY_MAP.get(priority_raw, "medium")
        tags_raw = str(cell(row, "Tags") or "").strip()
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []
        blocked_raw = str(cell(row, "Blocked By") or "").strip()
        blocked_by = [b.strip() for b in blocked_raw.split(",") if b.strip()]
        sub_raw = str(cell(row, "サブ担当者") or "").strip()
        sub_emails = [e.strip() for e in sub_raw.split(",") if e.strip()]
        result.append(
            AsanaRow(
                task_id=str(cell(row, "Task ID") or "").strip(),
                name=name,
                section=str(cell(row, "Section/Column") or "").strip(),
                assignee_email=str(cell(row, "Assignee") or "").strip(),
                due_date=_parse_date(cell(row, "Due Date")),
                start_date=_parse_date(cell(row, "Start Date")),
                completed_at=completed_at,
                is_completed=completed_at is not None,
                priority=priority,
                notes=str(cell(row, "Notes") or "").strip(),
                tags=tags,
                blocked_by=blocked_by,
                created_at=_parse_datetime(cell(row, "Created At")),
                parent_task_name=str(cell(row, "Parent task") or "").strip(),
                sub_assignee_emails=sub_emails,
            )
        )
    return result
