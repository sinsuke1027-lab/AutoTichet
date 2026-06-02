# タスク CSV エクスポート 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** タスク一覧ページに CSV エクスポートボタンを追加し、現在のフィルタ条件を適用した全タスクを UTF-8 BOM 付き CSV でダウンロードできるようにする。

**Architecture:** バックエンドに `GET /api/v1/tasks/export/csv` を `tasks_crud.py` へ追加（ページネーションなし・`selectinload` でプロジェクト/セクション名をロード）。フロントエンドは axios で `responseType: 'blob'` 取得 → 動的 `<a>` タグでダウンロード発火。

**Tech Stack:** Python 標準 `csv` + `io.StringIO`（依存追加なし）、FastAPI `StreamingResponse`、React + Ant Design、axios

---

## ファイル構成

| ファイル | 変更種別 |
|---------|---------|
| `tests/unit/test_task_csv_export.py` | 新規作成（5件） |
| `src/api/routers/tasks_crud.py` | 修正（import 追加・定数追加・エンドポイント追加） |
| `frontend/src/pages/Tasks/index.tsx` | 修正（ボタン追加） |

---

### Task 1: テストファイル作成

**Files:**
- Create: `tests/unit/test_task_csv_export.py`

- [ ] **Step 1: テストファイルを新規作成**

`tests/unit/test_task_csv_export.py` を以下の内容で作成:

```python
import csv
import io
import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.api.routers.tasks_crud import router
from src.db.engine import get_db
from src.db.models import Task

_admin = TokenPayload(
    sub="admin-1", name="Admin", email="a@t.com", roles=["admin"], tid="tid"
)


def _make_task(*, status: str = "not_started") -> MagicMock:
    t = MagicMock(spec=Task)
    t.id = uuid.uuid4()
    t.title = "テストタスク"
    t.status = status
    t.priority = "medium"
    t.assignee_id = "user-1"
    t.start_date = date(2026, 6, 1)
    t.due_date = date(2026, 6, 30)
    t.completed_at = None
    t.project_id = None
    t.section_id = None
    t.description = "テスト説明"
    t.confidence_score = None
    t.source_type = None
    t.created_at = datetime(2026, 6, 1, 0, 0, 0)
    t.updated_at = datetime(2026, 6, 1, 0, 0, 0)
    t.tags = []
    t.sub_assignees = []
    t.work_hours = []
    t.subtasks = []
    t.project = None
    t.section = None
    t.visibility = "all"
    return t


def _make_db(tasks: list) -> AsyncMock:
    mock_db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = tasks
    result.all.return_value = []
    mock_db.execute = AsyncMock(return_value=result)
    return mock_db


def _make_client(db: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _admin
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app, raise_server_exceptions=False)


def test_export_csv_returns_200_and_text_csv() -> None:
    """正常リクエスト → 200, Content-Type: text/csv"""
    task = _make_task()
    client = _make_client(_make_db([task]))
    resp = client.get("/api/v1/tasks/export/csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]


def test_export_csv_content_disposition() -> None:
    """Content-Disposition に attachment と filename が含まれる"""
    client = _make_client(_make_db([]))
    resp = client.get("/api/v1/tasks/export/csv")
    cd = resp.headers.get("content-disposition", "")
    assert "attachment" in cd
    assert "tasks_" in cd
    assert ".csv" in cd


def test_export_csv_utf8_bom() -> None:
    """レスポンスが UTF-8 BOM 付きであること"""
    task = _make_task()
    client = _make_client(_make_db([task]))
    resp = client.get("/api/v1/tasks/export/csv")
    assert resp.content[:3] == b"\xef\xbb\xbf"


def test_export_csv_status_filter_row_value() -> None:
    """status=completed クエリパラメータ → CSV の ステータス 列が completed"""
    task = _make_task(status="completed")
    client = _make_client(_make_db([task]))
    resp = client.get("/api/v1/tasks/export/csv?status=completed")
    assert resp.status_code == 200
    reader = csv.DictReader(io.StringIO(resp.content.decode("utf-8-sig")))
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["ステータス"] == "completed"


def test_export_csv_has_20_headers() -> None:
    """CSV ヘッダーが 20 列あること（ID〜更新日時）"""
    client = _make_client(_make_db([]))
    resp = client.get("/api/v1/tasks/export/csv")
    reader = csv.reader(io.StringIO(resp.content.decode("utf-8-sig")))
    headers = next(reader)
    assert len(headers) == 20
    assert headers[0] == "ID"
    assert headers[1] == "タイトル"
    assert headers[-1] == "更新日時"
```

- [ ] **Step 2: テストを実行して FAIL を確認**

```bash
pytest tests/unit/test_task_csv_export.py -v
```

期待: `FAILED` — `/export/csv` エンドポイントが存在しないため 404 → アサーション失敗

---

### Task 2: バックエンドエンドポイント実装

**Files:**
- Modify: `src/api/routers/tasks_crud.py`

- [ ] **Step 1: import セクションに `csv`・`io`・`StreamingResponse` を追加**

`src/api/routers/tasks_crud.py` の先頭 import を以下に変更（既存 import に2行追加）:

変更前:
```python
import logging
import re
import uuid
from collections import deque
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
```

変更後:
```python
import csv
import io
import logging
import re
import uuid
from collections import deque
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
```

- [ ] **Step 2: `_CSV_HEADERS` 定数を `_compute_risk_level` の直前（line 53 付近）に追加**

`_CSV_HEADERS` を以下の位置に挿入（`DbDep = ...` の行の直後、`def _compute_risk_level` の直前）:

```python
_CSV_HEADERS = [
    "ID", "タイトル", "ステータス", "優先度", "担当者", "サブ担当者",
    "開始日", "期限日", "完了日時", "プロジェクト名", "セクション名",
    "タグ", "説明", "見積工数(h)", "実績工数(h)", "リスクレベル",
    "信頼スコア", "ソース種別", "作成日時", "更新日時",
]
```

- [ ] **Step 3: `export_tasks_csv` エンドポイントを `GET /{task_id}` の直前（line 434 付近）に追加**

`@router.get("/{task_id}", ...)` の直前に以下を挿入:

```python
@router.get("/export/csv")
async def export_tasks_csv(
    db: DbDep,
    current_user: CurrentUser,
    status_filter: TaskStatus | None = Query(default=None, alias="status"),  # noqa: B008
    assignee: str | None = None,
    project_id: uuid.UUID | None = None,
    section_id: uuid.UUID | None = None,
    tag: str | None = None,
    q: str | None = None,
    due_date_gte: date | None = Query(default=None),
    due_date_lte: date | None = Query(default=None),
    assignee_ids: list[str] | None = Query(default=None),
    my_tasks_only: bool = Query(default=False),
    include_archived_projects: bool = Query(default=False),
) -> StreamingResponse:
    query = select(Task).options(
        selectinload(Task.tags),
        selectinload(Task.sub_assignees),
        selectinload(Task.work_hours),
        selectinload(Task.project),
        selectinload(Task.section),
    )
    if status_filter:
        query = query.where(Task.status == status_filter.value)
    if assignee:
        query = query.where(Task.assignee_id == assignee)
    if project_id:
        query = query.where(Task.project_id == project_id)
    if section_id:
        query = query.where(Task.section_id == section_id)
    if tag:
        query = query.where(Task.id.in_(select(TaskTag.task_id).where(TaskTag.tag == tag)))
    if q:
        like = f"%{q}%"
        query = query.where(Task.title.ilike(like) | Task.description.ilike(like))
    if due_date_gte:
        query = query.where(Task.due_date >= due_date_gte)
    if due_date_lte:
        query = query.where(Task.due_date <= due_date_lte)
    if assignee_ids:
        query = query.where(Task.assignee_id.in_(assignee_ids))
    if my_tasks_only:
        query = query.where(
            Task.assignee_id == current_user.sub,
            Task.visibility == "private",
        )
    user_role = max(
        (ROLE_HIERARCHY.get(r, 0) for r in current_user.roles),
        default=0,
    )
    if not my_tasks_only and user_role < ROLE_HIERARCHY["manager"]:
        if user_role >= ROLE_HIERARCHY["leader"]:
            if current_user.department_tags:
                dept_result = await db.execute(
                    select(UserProfile.user_id).where(
                        UserProfile.department_tags.op("?|")(pg_array(current_user.department_tags))
                    )
                )
                dept_user_ids = list(dept_result.scalars().all())
                query = query.where(
                    or_(
                        Task.assignee_id.in_(dept_user_ids),
                        Task.visibility == "all",
                    )
                )
            else:
                query = query.where(Task.visibility == "all")
        else:
            query = query.where(
                or_(
                    Task.assignee_id == current_user.sub,
                    Task.visibility == "all",
                )
            )
    if not include_archived_projects:
        query = query.outerjoin(Project, Task.project_id == Project.id).where(
            or_(Task.project_id.is_(None), Project.status != "archived")
        )

    result = await db.execute(query.order_by(Task.due_date.asc().nulls_last()))
    tasks = result.scalars().all()

    output = io.StringIO()
    output.write("﻿")  # UTF-8 BOM（Excel 文字化け防止）
    writer = csv.writer(output)
    writer.writerow(_CSV_HEADERS)
    for task in tasks:
        wh = task.work_hours[0] if task.work_hours else None
        writer.writerow([
            str(task.id),
            task.title,
            task.status,
            task.priority,
            task.assignee_id or "",
            ",".join(a.user_id for a in task.sub_assignees),
            str(task.start_date) if task.start_date else "",
            str(task.due_date) if task.due_date else "",
            task.completed_at.isoformat() if task.completed_at else "",
            task.project.name if task.project else "",
            task.section.name if task.section else "",
            ",".join(t.tag for t in task.tags),
            task.description or "",
            str(wh.estimated_hours) if wh and wh.estimated_hours is not None else "",
            str(wh.actual_hours) if wh and wh.actual_hours is not None else "",
            _compute_risk_level(task) or "",
            str(task.confidence_score) if task.confidence_score is not None else "",
            task.source_type or "",
            task.created_at.isoformat(),
            task.updated_at.isoformat(),
        ])

    filename = f"tasks_{date.today().strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
```

- [ ] **Step 4: テストを実行して PASS を確認**

```bash
pytest tests/unit/test_task_csv_export.py -v
```

期待: 5件すべて PASSED

- [ ] **Step 5: 全テストを実行して既存テストに回帰がないことを確認**

```bash
pytest tests/ -v
```

期待: 全件 PASSED（新規 5 件を含む）

- [ ] **Step 6: コミット**

```bash
git add tests/unit/test_task_csv_export.py src/api/routers/tasks_crud.py
git commit -m "feat: タスク CSV エクスポートエンドポイントを追加"
```

---

### Task 3: フロントエンドボタン追加

**Files:**
- Modify: `frontend/src/pages/Tasks/index.tsx`

- [ ] **Step 1: `DownloadOutlined` をアイコンインポートに追加**

`frontend/src/pages/Tasks/index.tsx` の line 23:

変更前:
```typescript
import { CopyOutlined, FileTextOutlined, PlusOutlined, RobotOutlined, SearchOutlined } from '@ant-design/icons'
```

変更後:
```typescript
import { CopyOutlined, DownloadOutlined, FileTextOutlined, PlusOutlined, RobotOutlined, SearchOutlined } from '@ant-design/icons'
```

- [ ] **Step 2: `api` をデフォルトインポートとして追加**

line 33-34:

変更前:
```typescript
import { generateHandover } from '../../lib/api'
```

変更後:
```typescript
import api, { generateHandover } from '../../lib/api'
```

- [ ] **Step 3: `handleExportCsv` 関数を `handleSearch` の直後に追加**

`const handleSearch = () => setSearchQ(keyword)` の次の行に追加:

```typescript
const handleExportCsv = async () => {
  const params: Record<string, string> = {}
  if (statusFilter) params['status'] = statusFilter
  if (projectFilter) params['project_id'] = projectFilter
  if (sectionFilter) params['section_id'] = sectionFilter
  if (assigneeFilter) params['assignee'] = assigneeFilter
  if (searchQ) params['q'] = searchQ
  if (myTasksOnly) params['my_tasks_only'] = 'true'
  if (includeArchivedProjects) params['include_archived_projects'] = 'true'

  try {
    const { data } = await api.get<Blob>('/tasks/export/csv', {
      params,
      responseType: 'blob',
    })
    const url = URL.createObjectURL(data)
    const a = document.createElement('a')
    a.href = url
    a.download = `tasks_${new Date().toISOString().slice(0, 10).replace(/-/g, '')}.csv`
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    void message.error('CSV のエクスポートに失敗しました')
  }
}
```

- [ ] **Step 4: CSV エクスポートボタンを「引き継ぎ書を生成」ボタンの直前に追加**

ヘッダー行の `<Space>` 内（「引き継ぎ書を生成」ボタンの直前）に追加:

変更前（line 229 付近）:
```tsx
          <Button
            icon={<FileTextOutlined />}
            loading={generateHandoverMutation.isPending}
```

変更後:
```tsx
          <Button icon={<DownloadOutlined />} onClick={() => void handleExportCsv()}>
            CSV エクスポート
          </Button>
          <Button
            icon={<FileTextOutlined />}
            loading={generateHandoverMutation.isPending}
```

- [ ] **Step 5: TypeScript コンパイルチェック**

```bash
cd frontend && npx tsc --noEmit
```

期待: エラー 0件

- [ ] **Step 6: コミット**

```bash
git add frontend/src/pages/Tasks/index.tsx
git commit -m "feat: タスク一覧に CSV エクスポートボタンを追加"
```
