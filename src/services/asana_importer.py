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

# "Name" 列を持つ行をヘッダーとして自動検出する際の検索上限行数
_HEADER_SEARCH_LIMIT = 10


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


def _find_header_row(rows: list[tuple]) -> int:
    """先頭 _HEADER_SEARCH_LIMIT 行の中から 'Name' 列を持つ行のインデックスを返す。
    見つからない場合は 0 を返す。"""
    for i, row in enumerate(rows[:_HEADER_SEARCH_LIMIT]):
        if any(str(v).strip() == "Name" for v in row if v is not None):
            return i
    return 0


def parse_asana_xlsx(xlsx_bytes: bytes) -> list[AsanaRow]:
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        return []

    # Asana エクスポートはタイトル行が先頭に入るため、ヘッダー行を自動検出する
    header_idx = _find_header_row(rows)
    headers = [str(h).strip() if h is not None else "" for h in rows[header_idx]]
    data_rows = rows[header_idx + 1 :]

    def cell(row: tuple, col: str) -> Any:
        try:
            idx = headers.index(col)
            return row[idx]
        except ValueError:
            return None

    def cell_ja(row: tuple, ja_col: str, en_col: str | None = None) -> Any:
        v = cell(row, ja_col)
        if v is None and en_col:
            v = cell(row, en_col)
        return v

    # 担当者メールアドレス列: テンプレートは "Assignee Email"、
    # 旧 Asana エクスポートは "Assignee" にメールが入る場合もあるため両方試みる
    def assignee_email(row: tuple) -> str:
        v = cell(row, "Assignee Email") or cell(row, "Assignee")
        return str(v or "").strip()

    # 依存関係列: テンプレートは "Blocked By (Dependencies)"、
    # 旧形式は "Blocked By" を許容する
    def blocked_by_raw(row: tuple) -> str:
        v = cell(row, "Blocked By (Dependencies)") or cell(row, "Blocked By")
        return str(v or "").strip()

    result: list[AsanaRow] = []
    for row in data_rows:
        name = str(cell_ja(row, "タイトル", "Name") or "").strip()
        if not name:
            continue
        completed_at_raw = cell_ja(row, "完了日時", "Completed At")
        completed_at = _parse_datetime(completed_at_raw)
        priority_raw = str(cell_ja(row, "優先度") or "").strip()
        priority = _PRIORITY_MAP.get(priority_raw, "medium")
        tags_raw = str(cell_ja(row, "タグ", "Tags") or "").strip()
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []
        blocked_raw = str(
            cell_ja(row, "依存関係（ブロック元）", "Blocked By (Dependencies)")
            or cell(row, "Blocked By")
            or ""
        ).strip()
        blocked_by = [b.strip() for b in blocked_raw.split(",") if b.strip()]
        sub_raw = str(cell_ja(row, "サブ担当者") or "").strip()
        sub_emails = [e.strip() for e in sub_raw.split(",") if e.strip()]
        result.append(
            AsanaRow(
                task_id=str(cell_ja(row, "ID", "Task ID") or "").strip(),
                name=name,
                section=str(cell_ja(row, "セクション名", "Section/Column") or "").strip(),
                assignee_email=str(
                    cell_ja(row, "担当者", "Assignee Email") or cell(row, "Assignee") or ""
                ).strip(),
                due_date=_parse_date(cell_ja(row, "期限日", "Due Date")),
                start_date=_parse_date(cell_ja(row, "開始日", "Start Date")),
                completed_at=completed_at,
                is_completed=completed_at is not None,
                priority=priority,
                notes=str(cell_ja(row, "説明", "Notes") or "").strip(),
                tags=tags,
                blocked_by=blocked_by,
                created_at=_parse_datetime(cell_ja(row, "作成日時", "Created At")),
                parent_task_name=str(cell_ja(row, "親タスク名", "Parent task") or "").strip(),
                sub_assignee_emails=sub_emails,
            )
        )
    return result
