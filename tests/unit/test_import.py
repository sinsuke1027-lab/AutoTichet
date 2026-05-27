import io
from datetime import date

import openpyxl

from src.services.asana_importer import parse_asana_xlsx


def _make_xlsx(rows: list[dict]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    headers = [
        "Task ID", "Name", "Section/Column", "Assignee", "Due Date", "Start Date",
        "Completed At", "優先度", "Notes", "Tags", "Blocked By", "Created At",
        "Parent task", "サブ担当者",
    ]
    ws.append(headers)
    for row in rows:
        ws.append([row.get(h, "") for h in headers])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_parse_empty_xlsx_returns_empty() -> None:
    result = parse_asana_xlsx(_make_xlsx([]))
    assert result == []


def test_parse_single_task_row() -> None:
    rows = [{
        "Task ID": "12345",
        "Name": "テストタスク",
        "Section/Column": "バックオフィス",
        "Assignee": "test@example.com",
        "Due Date": "2026/06/30",
        "Start Date": "",
        "Completed At": "",
        "優先度": "高",
        "Notes": "説明文",
        "Tags": "",
        "Blocked By": "",
        "Created At": "2026/01/01",
        "Parent task": "",
        "サブ担当者": "",
    }]
    result = parse_asana_xlsx(_make_xlsx(rows))
    assert len(result) == 1
    r = result[0]
    assert r.task_id == "12345"
    assert r.name == "テストタスク"
    assert r.section == "バックオフィス"
    assert r.assignee_email == "test@example.com"
    assert r.priority == "high"
    assert r.notes == "説明文"
    assert r.due_date == date(2026, 6, 30)
    assert r.completed_at is None


def test_parse_completed_task() -> None:
    rows = [{
        "Task ID": "99", "Name": "完了タスク", "Section/Column": "", "Assignee": "",
        "Due Date": "", "Start Date": "", "Completed At": "2026/03/15 10:00:00",
        "優先度": "最高", "Notes": "", "Tags": "", "Blocked By": "",
        "Created At": "", "Parent task": "", "サブ担当者": "",
    }]
    result = parse_asana_xlsx(_make_xlsx(rows))
    assert result[0].is_completed is True
    assert result[0].priority == "urgent"


def test_priority_mapping() -> None:
    cases = [
        ("最高", "urgent"), ("高", "high"), ("中", "medium"),
        ("低", "low"), ("", "medium"), ("unknown", "medium"),
    ]
    for asana_priority, expected in cases:
        rows = [{
            "Task ID": "1", "Name": "T", "Section/Column": "", "Assignee": "",
            "Due Date": "", "Start Date": "", "Completed At": "",
            "優先度": asana_priority, "Notes": "", "Tags": "", "Blocked By": "",
            "Created At": "", "Parent task": "", "サブ担当者": "",
        }]
        result = parse_asana_xlsx(_make_xlsx(rows))
        assert result[0].priority == expected, f"Failed for '{asana_priority}'"


def test_sub_assignees_parsed() -> None:
    rows = [{
        "Task ID": "1", "Name": "T", "Section/Column": "", "Assignee": "main@example.com",
        "Due Date": "", "Start Date": "", "Completed At": "",
        "優先度": "", "Notes": "", "Tags": "", "Blocked By": "",
        "Created At": "", "Parent task": "", "サブ担当者": "a@x.com, b@x.com",
    }]
    result = parse_asana_xlsx(_make_xlsx(rows))
    assert result[0].sub_assignee_emails == ["a@x.com", "b@x.com"]
