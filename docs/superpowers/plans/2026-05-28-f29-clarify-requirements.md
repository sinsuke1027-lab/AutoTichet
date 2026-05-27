# F-29 タスク要件の明確化プロンプト Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** タスク詳細の「詳細」タブに「AI チェック」ボタンを追加し、押下時にルールベース + Gemini でタスクの不足項目（期限・担当者・完了条件）を検知して Alert で表示する。

**Architecture:** バックエンドは `POST /tasks/{id}/clarify-requirements` エンドポイントがルールチェック（due_date・assignees）と Gemini AI（description 品質）を組み合わせて issues リストを返す。フロントエンドは `useMutation` フックで呼び出し、結果を `Alert` コンポーネントで表示する。Gemini API キー未設定時はルールチェック結果のみ返し 503 にしない。

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy 2.x async（selectinload）, Gemini API（google-genai）, React 18, TanStack Query v5（useMutation）, Ant Design 5.x（Alert, Button）

---

## ファイル変更マップ

| ファイル | 変更内容 |
|---------|---------|
| Modify: `src/models/task_web.py` | `ClarifyIssue` / `ClarifyRequirementsResponse` モデル追加 |
| Modify: `src/providers/gemini.py` | `_CLARIFY_SYSTEM` 定数 + `clarify_requirements()` メソッド追加 |
| Modify: `src/api/routers/tasks_crud.py` | import 追加 + `POST /{task_id}/clarify-requirements` エンドポイント追加 |
| Create: `tests/unit/test_clarify_requirements.py` | 6件のユニットテスト |
| Modify: `frontend/src/hooks/useTaskDetails.ts` | `ClarifyIssue` / `ClarifyRequirementsData` インターフェース + `useClarifyRequirements()` フック追加 |
| Modify: `frontend/src/pages/Tasks/TaskDetail.tsx` | AI チェックボタン + Alert 表示追加 |

---

### Task 1: Pydantic モデル + Gemini メソッド

**Files:**
- Modify: `src/models/task_web.py` （L459 末尾に追記）
- Modify: `src/providers/gemini.py` （L65 末尾に追記）

#### 背景

- `src/models/task_web.py` は現在 L459 で終わっている（`PastPerformanceResponse` が最後のクラス）
- `src/providers/gemini.py` は現在 L65 で終わっている（`generate_subtasks` が最後のメソッド）
- `_CLARIFY_SYSTEM` 定数は `_SUBTASK_SYSTEM`（L9）と同じ形式で追加する

- [ ] **Step 1: Pydantic モデルをファイル末尾に追記する**

`src/models/task_web.py` の末尾（L459 の後）に追記:

```python


class ClarifyIssue(BaseModel):
    field: str  # "due_date" | "assignees" | "description"
    message: str
    suggestion: str | None  # AI提案文（descriptionのみ）


class ClarifyRequirementsResponse(BaseModel):
    issues: list[ClarifyIssue]
```

- [ ] **Step 2: Gemini メソッドをファイル末尾に追記する**

`src/providers/gemini.py` の末尾（L65 の後）に追記:

```python


_CLARIFY_SYSTEM = (
    "あなたはプロジェクト管理の専門家です。"
    "タスクのタイトルと説明を読み、完了条件が明確かどうかを判断してください。"
    "以下のJSON形式のみで返してください:\n"
    '{"has_issue": true/false, "suggestion": "改善提案（has_issueがtrueの場合のみ、1〜2文）"}\n'
    "has_issueをtrueにする条件:\n"
    "- 説明が存在しないか極めて短い（意味のある内容が10文字未満）\n"
    "- 何をもって完了とするかが不明確\n"
    "- 抽象的すぎて具体的なアクションが見えない\n"
    "上記に当てはまらない場合はhas_issue: falseを返してください。"
)
```

`GeminiProvider` クラスの末尾（`generate_subtasks` メソッドの後）に追記:

```python
    async def clarify_requirements(self, title: str, description: str | None) -> str | None:
        prompt = f"タスクタイトル: {title}\n説明: {description or '（未記載）'}"
        resp = await self._client.aio.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_CLARIFY_SYSTEM,
                response_mime_type="application/json",
            ),
        )
        try:
            data: dict[str, object] = json.loads(resp.text or '{"has_issue": false}')
            if data.get("has_issue"):
                return str(data.get("suggestion", ""))
            return None
        except json.JSONDecodeError:
            return None
```

- [ ] **Step 3: コミットする**

```powershell
git add src/models/task_web.py src/providers/gemini.py
git commit -m "feat: F-29 ClarifyIssue モデルと GeminiProvider.clarify_requirements 追加"
```

---

### Task 2: バックエンドエンドポイント + テスト

**Files:**
- Modify: `src/api/routers/tasks_crud.py` （L18-28 の import 追加 + L464 末尾にエンドポイント追加）
- Create: `tests/unit/test_clarify_requirements.py`

#### 背景

- `tasks_crud.py` の import 部分（L18-28）に `ClarifyIssue` と `ClarifyRequirementsResponse` を追加する
- 既存の `generate_subtasks` エンドポイント（L443-464）の直後にエンドポイントを追加する
- Task の `sub_assignees` リレーションシップ（`src/db/models.py` L93）を `selectinload` でロードする
- テストのモック形式は `tests/unit/test_generate_subtasks.py` と同じパターンを踏襲する

- [ ] **Step 1: テストファイルを作成して最初のテストを書く**

`tests/unit/test_clarify_requirements.py` を新規作成:

```python
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.api.routers.tasks_crud import router
from src.db.engine import get_db

_user = TokenPayload(sub="user-1", name="Test", email="t@t.com", roles=["member"], tid="tid")


def _make_client(mock_db: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _user
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app, raise_server_exceptions=False)


def _make_task(
    *,
    due_date=None,
    sub_assignees=None,
    description=None,
) -> MagicMock:
    from src.db.models import Task

    task = MagicMock(spec=Task)
    task.id = uuid.uuid4()
    task.title = "テストタスク"
    task.description = description
    task.due_date = due_date
    task.sub_assignees = sub_assignees if sub_assignees is not None else []
    return task


def test_clarify_due_date_missing() -> None:
    """due_date が null の場合 due_date issue が返る"""
    mock_task = _make_task(due_date=None, sub_assignees=[MagicMock()])
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_task
    mock_db.execute = AsyncMock(return_value=mock_result)

    client = _make_client(mock_db)
    with patch("src.api.routers.tasks_crud.GeminiProvider") as MockProvider:
        instance = MockProvider.return_value
        instance.clarify_requirements = AsyncMock(return_value=None)
        resp = client.post(f"/api/v1/tasks/{mock_task.id}/clarify-requirements")

    assert resp.status_code == 200
    data = resp.json()
    fields = [i["field"] for i in data["issues"]]
    assert "due_date" in fields
    assert "assignees" not in fields
```

- [ ] **Step 2: テストが失敗することを確認する**

```powershell
python -m pytest tests/unit/test_clarify_requirements.py::test_clarify_due_date_missing -v
```

期待結果: FAIL（エンドポイントが未実装のため）

- [ ] **Step 3: `tasks_crud.py` の import に `ClarifyIssue`・`ClarifyRequirementsResponse` を追加する**

`src/api/routers/tasks_crud.py` の L18-28 の import ブロックを以下に変更:

```python
from src.models.task_web import (
    ClarifyIssue,
    ClarifyRequirementsResponse,
    GenerateSubtasksResponse,
    RescheduleRequest,
    RescheduleResponse,
    SimilarTaskResponse,
    TaskCreate,
    TaskListResponse,
    TaskResponse,
    TaskStatus,
    TaskUpdate,
)
```

- [ ] **Step 4: エンドポイントをファイル末尾（L464 の後）に追加する**

`src/api/routers/tasks_crud.py` の末尾（`generate_subtasks` の後）に追記:

```python


@router.post("/{task_id}/clarify-requirements", response_model=ClarifyRequirementsResponse)
async def clarify_requirements_endpoint(
    task_id: uuid.UUID, db: DbDep, current_user: CurrentUser
) -> ClarifyRequirementsResponse:
    result = await db.execute(
        select(Task).options(selectinload(Task.sub_assignees)).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="タスクが見つかりません")

    issues: list[ClarifyIssue] = []

    if task.due_date is None:
        issues.append(
            ClarifyIssue(field="due_date", message="期限が設定されていません", suggestion=None)
        )

    if not task.sub_assignees:
        issues.append(
            ClarifyIssue(field="assignees", message="担当者が設定されていません", suggestion=None)
        )

    settings = get_settings()
    if settings.google_api_key:
        provider = GeminiProvider(api_key=settings.google_api_key, model=settings.gemini_model)
        try:
            suggestion = await provider.clarify_requirements(task.title, task.description)
            if suggestion:
                issues.append(
                    ClarifyIssue(
                        field="description",
                        message="完了条件が不明確です",
                        suggestion=suggestion,
                    )
                )
        except Exception:
            logger.exception("Gemini clarify_requirements failed for task %s", task_id)

    return ClarifyRequirementsResponse(issues=issues)
```

- [ ] **Step 5: 最初のテストが通ることを確認する**

```powershell
python -m pytest tests/unit/test_clarify_requirements.py::test_clarify_due_date_missing -v
```

期待結果: PASS

- [ ] **Step 6: 残り5件のテストを追加する**

`tests/unit/test_clarify_requirements.py` に以下を追記:

```python
def test_clarify_assignees_missing() -> None:
    """assignees が空の場合 assignees issue が返る"""
    from datetime import date

    mock_task = _make_task(due_date=date.today(), sub_assignees=[])
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_task
    mock_db.execute = AsyncMock(return_value=mock_result)

    client = _make_client(mock_db)
    with patch("src.api.routers.tasks_crud.GeminiProvider") as MockProvider:
        instance = MockProvider.return_value
        instance.clarify_requirements = AsyncMock(return_value=None)
        resp = client.post(f"/api/v1/tasks/{mock_task.id}/clarify-requirements")

    assert resp.status_code == 200
    data = resp.json()
    fields = [i["field"] for i in data["issues"]]
    assert "assignees" in fields
    assert "due_date" not in fields


def test_clarify_no_issues() -> None:
    """due_date あり・assignees あり・Gemini 問題なし → issues 空"""
    from datetime import date

    mock_task = _make_task(
        due_date=date.today(),
        sub_assignees=[MagicMock()],
        description="ユーザーが〇〇できたら完了とする",
    )
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_task
    mock_db.execute = AsyncMock(return_value=mock_result)

    client = _make_client(mock_db)
    with patch("src.api.routers.tasks_crud.GeminiProvider") as MockProvider:
        instance = MockProvider.return_value
        instance.clarify_requirements = AsyncMock(return_value=None)
        resp = client.post(f"/api/v1/tasks/{mock_task.id}/clarify-requirements")

    assert resp.status_code == 200
    assert resp.json()["issues"] == []


def test_clarify_task_not_found() -> None:
    """タスク不存在 → 404"""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    client = _make_client(mock_db)
    resp = client.post(f"/api/v1/tasks/{uuid.uuid4()}/clarify-requirements")
    assert resp.status_code == 404


def test_clarify_no_api_key_returns_rule_issues_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gemini APIキー未設定 → ルールチェック結果のみ返し 503 にならない"""
    from src.models.config import Settings

    empty_settings = Settings(
        google_api_key="",
        database_url="postgresql+asyncpg://x:x@localhost/x",
    )

    mock_task = _make_task(due_date=None, sub_assignees=[])
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_task
    mock_db.execute = AsyncMock(return_value=mock_result)

    client = _make_client(mock_db)
    with patch("src.api.routers.tasks_crud.get_settings", return_value=empty_settings):
        resp = client.post(f"/api/v1/tasks/{mock_task.id}/clarify-requirements")

    assert resp.status_code == 200
    data = resp.json()
    fields = [i["field"] for i in data["issues"]]
    assert "due_date" in fields
    assert "assignees" in fields
    assert "description" not in fields


def test_clarify_gemini_detects_issue() -> None:
    """Gemini が有問題と判定 → description issue が含まれる"""
    from datetime import date

    mock_task = _make_task(
        due_date=date.today(),
        sub_assignees=[MagicMock()],
        description="なんかやる",
    )
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_task
    mock_db.execute = AsyncMock(return_value=mock_result)

    client = _make_client(mock_db)
    with patch("src.api.routers.tasks_crud.GeminiProvider") as MockProvider:
        instance = MockProvider.return_value
        instance.clarify_requirements = AsyncMock(
            return_value="「〇〇が完了したら終了」のような受け入れ基準を追加してください"
        )
        resp = client.post(f"/api/v1/tasks/{mock_task.id}/clarify-requirements")

    assert resp.status_code == 200
    data = resp.json()
    desc_issues = [i for i in data["issues"] if i["field"] == "description"]
    assert len(desc_issues) == 1
    assert desc_issues[0]["suggestion"] is not None
    assert desc_issues[0]["suggestion"] != ""
```

- [ ] **Step 7: 全テストを実行して通過を確認する**

```powershell
python -m pytest tests/unit/test_clarify_requirements.py -v
```

期待結果: 6 passed

- [ ] **Step 8: コミットする**

```powershell
git add src/api/routers/tasks_crud.py tests/unit/test_clarify_requirements.py
git commit -m "feat: F-29 clarify-requirements エンドポイント追加・テスト 6 件"
```

---

### Task 3: フロントエンド

**Files:**
- Modify: `frontend/src/hooks/useTaskDetails.ts` （L129 末尾に追記）
- Modify: `frontend/src/pages/Tasks/TaskDetail.tsx` （import 変更 + state + ハンドラ + UI 追加）

#### 背景

- `useTaskDetails.ts` は現在 L129 で終わっている（`usePastPerformance` が最後）
- `TaskDetail.tsx` は Ant Design の `Button, Descriptions, message, Popconfirm, Select, Space, Spin, Tabs, Tag, Typography` を import 済み。`Alert` は未 import
- `TaskDetail.tsx` の詳細タブ children は L85-121 の `<Descriptions>` ブロック

- [ ] **Step 1: `useClarifyRequirements` フックを `useTaskDetails.ts` 末尾に追記する**

```typescript
interface ClarifyIssue {
  field: string
  message: string
  suggestion: string | null
}

interface ClarifyRequirementsData {
  issues: ClarifyIssue[]
}

export function useClarifyRequirements(taskId: string) {
  return useMutation<ClarifyRequirementsData>({
    mutationFn: async () => {
      const { data } = await api.post<ClarifyRequirementsData>(
        `/tasks/${taskId}/clarify-requirements`,
      )
      return data
    },
  })
}
```

- [ ] **Step 2: `TaskDetail.tsx` を更新する**

`frontend/src/pages/Tasks/TaskDetail.tsx` を以下の変更を加える:

**2a. antd import に `Alert` を追加（L3-14 を変更）:**

```typescript
import {
  Alert,
  Button,
  Descriptions,
  message,
  Popconfirm,
  Select,
  Space,
  Spin,
  Tabs,
  Tag,
  Typography,
} from 'antd'
```

**2b. hooks import に `useClarifyRequirements` を追加（L16-17 を変更）:**

```typescript
import { useTask, useUpdateTask, useDeleteTask } from '../../hooks/useTasks'
import { useSections } from '../../hooks/useSections'
import { useClarifyRequirements } from '../../hooks/useTaskDetails'
```

**2c. `AppLayout` 関数内の既存 state 宣言群（L44 の後）に追加:**

```typescript
const clarify = useClarifyRequirements(id ?? '')
```

**2d. 詳細タブの `children`（L84-121）を以下に変更:**

```typescript
      children: (
        <Space direction="vertical" style={{ width: '100%' }}>
          <Descriptions bordered column={1} size="small">
            <Descriptions.Item label="ステータス">
              <Select
                value={task.status}
                options={STATUS_OPTIONS}
                onChange={(v) => handleFieldChange('status', v)}
                style={{ width: 140 }}
              />
            </Descriptions.Item>
            <Descriptions.Item label="優先度">
              <Select
                value={task.priority}
                options={PRIORITY_OPTIONS}
                onChange={(v) => handleFieldChange('priority', v)}
                style={{ width: 120 }}
              />
            </Descriptions.Item>
            <Descriptions.Item label="セクション">
              <Select
                value={task.section_id ?? undefined}
                allowClear
                options={sections.map((s) => ({ label: s.name, value: s.id }))}
                onChange={(v: string | undefined) => handleFieldChange('section_id', v ?? null)}
                style={{ width: 200 }}
              />
            </Descriptions.Item>
            <Descriptions.Item label="期限">{task.due_date ?? '—'}</Descriptions.Item>
            <Descriptions.Item label="公開範囲">{task.visibility}</Descriptions.Item>
            <Descriptions.Item label="タグ">
              {task.tags.map((t) => (
                <Tag key={t}>{t}</Tag>
              ))}
            </Descriptions.Item>
            <Descriptions.Item label="説明">{task.description ?? '—'}</Descriptions.Item>
          </Descriptions>
          <Button
            onClick={async () => {
              const result = await clarify.mutateAsync()
              if (result.issues.length === 0) {
                void message.success('問題は検出されませんでした')
              }
            }}
            loading={clarify.isPending}
          >
            🤖 AI チェック
          </Button>
          {clarify.data && clarify.data.issues.length > 0 && (
            <Alert
              type="warning"
              message="以下の項目を確認してください"
              description={
                <ul style={{ margin: 0, paddingLeft: 20 }}>
                  {clarify.data.issues.map((issue) => (
                    <li key={issue.field}>
                      {issue.message}
                      {issue.suggestion && (
                        <Typography.Text type="secondary">
                          {' — '}{issue.suggestion}
                        </Typography.Text>
                      )}
                    </li>
                  ))}
                </ul>
              }
            />
          )}
        </Space>
      ),
```

- [ ] **Step 3: TypeScript 型チェックを実行する**

```powershell
cd frontend
npx tsc --noEmit
```

期待結果: エラー出力なし（0 errors）

- [ ] **Step 4: コミットする**

```powershell
git add frontend/src/hooks/useTaskDetails.ts frontend/src/pages/Tasks/TaskDetail.tsx
git commit -m "feat: F-29 AI チェックボタンと要件不足 Alert を詳細タブに追加"
```
