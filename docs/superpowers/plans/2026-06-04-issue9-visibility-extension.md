# Issue #9 — 公開範囲拡張（特定タグ/特定プロジェクト）実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **推奨実行順:** `2026-06-04-issue10-project-members.md` の後（`project_members` テーブル使用のため）。

**Goal:** タスクの公開範囲（visibility）に「特定タグ」「特定プロジェクト」を追加し、指定した部門タグまたはプロジェクトメンバーのみが参照できるタスクを作成できるようにする。

**Architecture:** DB に `visibility_tag`・`visibility_project_id` 列を追加（Alembic 0011）→ バックエンドで新 visibility 値のスコープ判定を実装 → フロントのタスク作成モーダルで visibility 選択を拡張する。

**Tech Stack:** SQLAlchemy 2.x, Alembic, FastAPI, Pydantic v2, React 18 + TypeScript, Ant Design 5.x

---

## ファイルマップ

| 操作 | パス |
|-----|-----|
| 新規作成 | `alembic/versions/0011_visibility_ext.py` |
| 修正 | `src/db/models.py` — `Task` に 2 列追加 |
| 修正 | `src/models/task_web.py` — `TaskCreate` / `TaskUpdate` / `TaskResponse` に 2 フィールド追加 |
| 修正 | `src/api/routers/tasks_crud.py` — `list_tasks` スコープ判定に新 visibility 対応 |
| 修正 | `frontend/src/lib/api.ts` — `Task` 型に 2 フィールド追加 |
| 修正 | `frontend/src/pages/Tasks/index.tsx` — 作成モーダルの visibility Select 拡張 |
| 新規作成 | `tests/unit/test_visibility_ext.py` |

---

### Task 1: Alembic マイグレーション 0011

**Files:**
- Create: `alembic/versions/0011_visibility_ext.py`

- [ ] **Step 1: マイグレーションファイルを作成する**

```python
# alembic/versions/0011_visibility_ext.py
"""tasks テーブルに visibility_tag / visibility_project_id 列追加

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("visibility_tag", sa.Text, nullable=True))
    op.add_column(
        "tasks",
        sa.Column(
            "visibility_project_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("tasks", "visibility_project_id")
    op.drop_column("tasks", "visibility_tag")
```

- [ ] **Step 2: マイグレーションを適用する**

```bash
alembic upgrade head
```

期待出力: `Running upgrade 0010 -> 0011`

---

### Task 2: SQLAlchemy モデル更新 + テスト作成

**Files:**
- Modify: `src/db/models.py`
- Create: `tests/unit/test_visibility_ext.py`

- [ ] **Step 1: `Task` クラスに 2 列を追加する**

`src/db/models.py` の `Task` クラスの `recurrence_origin_id` 列（約 78 行目）の後に追加：

```python
    visibility_tag: Mapped[str | None] = mapped_column(Text, nullable=True)
    visibility_project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
    )
```

- [ ] **Step 2: テストを書く**

```python
# tests/unit/test_visibility_ext.py
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_task_visibility_tag(client: AsyncClient, auth_headers: dict) -> None:
    """visibility=tag のタスクが作成できる。"""
    r = await client.post(
        "/api/v1/tasks",
        json={
            "title": "Tag Visibility Task",
            "visibility": "tag",
            "visibility_tag": "人事部",
        },
        headers=auth_headers,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["visibility"] == "tag"
    assert data["visibility_tag"] == "人事部"


@pytest.mark.asyncio
async def test_create_task_visibility_project(
    client: AsyncClient, auth_headers: dict
) -> None:
    """visibility=project のタスクが作成できる。"""
    # プロジェクトを先に作成
    proj_r = await client.post(
        "/api/v1/projects", json={"name": "VisibilityProject"}, headers=auth_headers
    )
    project_id = proj_r.json()["id"]

    r = await client.post(
        "/api/v1/tasks",
        json={
            "title": "Project Visibility Task",
            "visibility": "project",
            "visibility_project_id": project_id,
        },
        headers=auth_headers,
    )
    assert r.status_code == 201
    assert r.json()["visibility"] == "project"
    assert r.json()["visibility_project_id"] == project_id


@pytest.mark.asyncio
async def test_visibility_tag_requires_visibility_tag_field(
    client: AsyncClient, auth_headers: dict
) -> None:
    """visibility=tag で visibility_tag が未指定なら 422。"""
    r = await client.post(
        "/api/v1/tasks",
        json={"title": "Missing Tag", "visibility": "tag"},
        headers=auth_headers,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_visibility_project_requires_project_id(
    client: AsyncClient, auth_headers: dict
) -> None:
    """visibility=project で visibility_project_id が未指定なら 422。"""
    r = await client.post(
        "/api/v1/tasks",
        json={"title": "Missing Project", "visibility": "project"},
        headers=auth_headers,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_tag_visibility_task_visible_to_same_dept(
    client: AsyncClient, auth_headers: dict
) -> None:
    """visibility=tag のタスクは同タグユーザーのタスク一覧に現れる。"""
    r = await client.get("/api/v1/tasks", headers=auth_headers)
    assert r.status_code == 200
```

- [ ] **Step 3: テストが失敗することを確認する**

```bash
pytest tests/unit/test_visibility_ext.py -v
```

期待: 失敗（フィールド未実装）

---

### Task 3: Pydantic モデル + バリデーション更新

**Files:**
- Modify: `src/models/task_web.py`

- [ ] **Step 1: `TaskCreate` に 2 フィールドを追加する**

`src/models/task_web.py` の `TaskCreate` クラス（`visibility` フィールドの後）に追加：

```python
    visibility_tag: str | None = None
    visibility_project_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def validate_visibility_fields(self) -> "TaskCreate":
        if self.visibility == "tag" and not self.visibility_tag:
            raise ValueError("visibility='tag' の場合は visibility_tag が必要です")
        if self.visibility == "project" and not self.visibility_project_id:
            raise ValueError("visibility='project' の場合は visibility_project_id が必要です")
        return self
```

- [ ] **Step 2: `TaskUpdate` に同フィールドを追加する**

`TaskUpdate` クラスの `visibility` フィールドの後に追加（Optional）：

```python
    visibility_tag: str | None = None
    visibility_project_id: uuid.UUID | None = None
```

- [ ] **Step 3: `TaskResponse` に 2 フィールドを追加する**

`TaskResponse` クラスの `project_name` フィールドの後に追加：

```python
    visibility_tag: str | None = None
    visibility_project_id: uuid.UUID | None = None
```

- [ ] **Step 4: `_task_to_response()` を更新する**

`src/api/routers/tasks_crud.py` の `_task_to_response()` 内の `return TaskResponse(` に追加：

```python
        visibility_tag=task.visibility_tag,
        visibility_project_id=task.visibility_project_id,
```

---

### Task 4: `list_tasks` スコープ判定に新 visibility 対応

**Files:**
- Modify: `src/api/routers/tasks_crud.py`

- [ ] **Step 1: `list_tasks` の `or_` 条件に新 visibility を追加する**

`list_tasks` のスコープフィルタ部分（`_scope.py` 対応後のブロック）の `or_` 条件を拡張する：

```python
    if not my_tasks_only:
        allowed_uids = await _visible_user_ids(db, current_user)
        if allowed_uids is not None:
            # visibility=tag: current_user の department_tags に visibility_tag が含まれる
            tag_condition = and_(
                Task.visibility == "tag",
                Task.visibility_tag.in_(current_user.department_tags or []),
            )
            # visibility=project: current_user が visibility_project_id のメンバーである
            from src.db.models import ProjectMember as PM
            member_project_ids_subq = (
                select(PM.project_id).where(PM.user_id == current_user.sub).scalar_subquery()
            )
            project_condition = and_(
                Task.visibility == "project",
                Task.visibility_project_id.in_(member_project_ids_subq),
            )
            query = query.where(
                or_(
                    Task.assignee_id.in_(allowed_uids),
                    Task.visibility == "all",
                    Task.created_by == current_user.sub,
                    tag_condition,
                    project_condition,
                )
            )
```

- [ ] **Step 2: `create_task` と `update_task` が新フィールドを保存することを確認する**

`tasks_crud.py` の `create_task` で `Task(...)` の引数に追加されているか確認し、不足なら追加する：

```python
    task = Task(
        ...
        visibility_tag=body.visibility_tag,
        visibility_project_id=body.visibility_project_id,
    )
```

`update_task` の `setattr` ループが `model_dump(exclude_none=True)` を使っていれば自動的に処理される（確認のみ）。

- [ ] **Step 3: テストを実行する**

```bash
pytest tests/unit/test_visibility_ext.py -v
```

期待: 5 件全 PASS

- [ ] **Step 4: コミットする**

```bash
git add alembic/versions/0011_visibility_ext.py src/db/models.py src/models/task_web.py src/api/routers/tasks_crud.py tests/unit/test_visibility_ext.py
git commit -m "feat: タスク公開範囲に特定タグ・特定プロジェクト visibility を追加 (#9)"
```

---

### Task 5: フロントエンド — visibility Select 拡張

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/pages/Tasks/index.tsx`

- [ ] **Step 1: `Task` 型に 2 フィールドを追加する**

`frontend/src/lib/api.ts` の `Task` インターフェースに追加：

```typescript
  visibility_tag?: string | null
  visibility_project_id?: string | null
```

- [ ] **Step 2: タスク作成モーダルの visibility Select を拡張する**

`frontend/src/pages/Tasks/index.tsx` の `Form.Item name="visibility"` ブロックを以下に置き換える：

```tsx
<Form.Item name="visibility" label="公開範囲" initialValue="team">
  <Select>
    <Select.Option value="private">個人</Select.Option>
    <Select.Option value="team">チーム共有</Select.Option>
    <Select.Option value="all">全員</Select.Option>
    <Select.Option value="tag">特定タグ</Select.Option>
    <Select.Option value="project">特定プロジェクト</Select.Option>
  </Select>
</Form.Item>

<Form.Item
  noStyle
  shouldUpdate={(prev, curr) => prev.visibility !== curr.visibility}
>
  {({ getFieldValue }) =>
    getFieldValue('visibility') === 'tag' ? (
      <Form.Item
        name="visibility_tag"
        label="対象タグ"
        rules={[{ required: true, message: '対象タグを選択してください' }]}
      >
        <Select
          options={adminTags.map((t) => ({ value: t.name, label: t.name }))}
          placeholder="部門タグを選択"
        />
      </Form.Item>
    ) : getFieldValue('visibility') === 'project' ? (
      <Form.Item
        name="visibility_project_id"
        label="対象プロジェクト"
        rules={[{ required: true, message: 'プロジェクトを選択してください' }]}
      >
        <Select
          options={projects.map((p) => ({ value: p.id, label: p.name }))}
          placeholder="プロジェクトを選択"
        />
      </Form.Item>
    ) : null
  }
</Form.Item>
```

`useProjects` と `useAdminTags` を import・使用していることを確認する（Task 4 で既に追加済み）。

`projects` 変数が未定義なら追加：

```typescript
const { data: projects = [] } = useProjects({ scope: 'mine' })
```

- [ ] **Step 3: タスク作成時のリクエストボディに新フィールドを含める**

タスク作成 `mutate` 呼び出し箇所で `values` に `visibility_tag`・`visibility_project_id` が含まれていることを確認する（`Form` の `onFinish` が `values` をそのまま渡す形なら自動で含まれる）。

- [ ] **Step 4: TypeScript ビルドを確認する**

```bash
cd frontend && npx tsc --noEmit
```

期待: エラーなし

- [ ] **Step 5: コミットする**

```bash
git add frontend/src/lib/api.ts frontend/src/pages/Tasks/index.tsx
git commit -m "feat: タスク作成モーダルの公開範囲に特定タグ・特定プロジェクトを追加 (#9)"
```

---

### Task 6: 全テスト実行・最終確認

- [ ] **Step 1: バックエンドテストを全件実行する**

```bash
pytest tests/ -v --tb=short
```

期待: 全 PASS

- [ ] **Step 2: フロントエンドビルドを確認する**

```bash
cd frontend && npm run build
```

- [ ] **Step 3: GitHub Issue をクローズする**

```bash
gh issue close 9 --repo sinsuke1027-lab/AutoTichet --comment "特定タグ・特定プロジェクト公開範囲の実装完了"
```
