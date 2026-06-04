# 部門タグ新規追加・説明文管理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 組織設定画面で部門タグを直接追加でき、各タグに説明文を付与・管理できるようにする（GitHub Issue #1）

**Architecture:** `department_tags` テーブル（`name PK`, `description`）を新設し、既存の `UserProfile.department_tags: list[str]` は変えない。`GET /admin/tags` の戻り値を `list[str]` から `list[DepartmentTagResponse]` に変更し、フロントエンドの型を更新する。既存ユーザーのタグはマイグレーション時に自動バックフィルする。

**Tech Stack:** FastAPI / SQLAlchemy 2.x async / Alembic / Pydantic v2 / React + TypeScript / Ant Design 5.x / TanStack Query

---

## ファイル構成

| ファイル | 変更 | 内容 |
|---------|------|------|
| `src/db/models.py` | 修正 | `DepartmentTag` ORM クラスを追加 |
| `alembic/versions/0009_department_tags_table.py` | 新規 | `department_tags` テーブル作成 + 既存タグをバックフィル |
| `src/models/task_web.py` | 修正 | `DepartmentTagCreate` / `DepartmentTagUpdate` / `DepartmentTagResponse` 追加、`TagRenameRequest` 削除 |
| `src/api/routers/admin.py` | 修正 | `GET/POST /admin/tags` 更新・追加、`PATCH /admin/tags/{tag}` を description 対応に拡張、`DELETE` を table 削除に対応 |
| `tests/unit/test_admin_tags.py` | 新規 | 5 件のユニットテスト（TDD） |
| `frontend/src/hooks/useAdminTags.ts` | 修正 | 型を `string[]` → `DepartmentTagResponse[]` に変更、`useCreateTag` / `useUpdateTag` を追加 |
| `frontend/src/pages/Admin/OrgSettings.tsx` | 修正 | 説明列追加・「タグを追加」ボタン + モーダル・編集モーダルに説明欄追加 |

---

## Task 1: SQLAlchemy モデル + Alembic 0009 マイグレーション

**Files:**
- Modify: `src/db/models.py`（`UserProfile` クラスの直後に追加）
- Create: `alembic/versions/0009_department_tags_table.py`

---

- [ ] **Step 1: `DepartmentTag` ORM クラスを `src/db/models.py` に追加**

`UserProfile` クラスの末尾（`class Section(Base):` の直前）に以下を挿入する:

```python
class DepartmentTag(Base):
    __tablename__ = "department_tags"

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 2: Alembic マイグレーション 0009 を作成**

`alembic/versions/0009_department_tags_table.py` を新規作成:

```python
"""department_tags table

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "department_tags",
        sa.Column("name", sa.Text(), primary_key=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # 既存ユーザーの department_tags 配列からバックフィル（重複は無視）
    op.execute(sa.text("""
        INSERT INTO department_tags (name)
        SELECT DISTINCT jsonb_array_elements_text(department_tags)
        FROM user_profiles
        WHERE department_tags IS NOT NULL AND department_tags != '[]'::jsonb
        ON CONFLICT (name) DO NOTHING
    """))


def downgrade() -> None:
    op.drop_table("department_tags")
```

- [ ] **Step 3: ローカルで alembic upgrade head を実行して動作確認**

```bash
alembic upgrade head
```

期待出力例（エラーなし）:
```
INFO  [alembic.runtime.migration] Running upgrade 0008 -> 0009, department_tags table
```

- [ ] **Step 4: コミット**

```bash
git add src/db/models.py alembic/versions/0009_department_tags_table.py
git commit -m "db: add department_tags table with description (Alembic 0009)"
```

---

## Task 2: Pydantic モデル + API エンドポイント（TDD）

**Files:**
- Create: `tests/unit/test_admin_tags.py`
- Modify: `src/models/task_web.py`（403 行目付近の `TagRenameRequest` を置換）
- Modify: `src/api/routers/admin.py`（タグ関連エンドポイント全体を書き替え）

---

- [ ] **Step 1: テストファイルを作成（まだ実装がないので全て失敗する）**

`tests/unit/test_admin_tags.py` を新規作成:

```python
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.api.routers.admin import router
from src.db.engine import get_db
from src.db.models import DepartmentTag

_admin = TokenPayload(sub="admin-1", name="Admin", email="a@a.com", roles=["admin"], tid="t")


@pytest.fixture()
def mock_db() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def client(mock_db: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _admin
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app, raise_server_exceptions=False)


def test_list_tags_returns_tag_objects(client: TestClient, mock_db: AsyncMock) -> None:
    """GET /admin/tags が DepartmentTagResponse のリストを返す"""
    tag = DepartmentTag(name="営業部", description="営業・提案担当")
    result = MagicMock()
    result.scalars.return_value.all.return_value = [tag]
    mock_db.execute = AsyncMock(return_value=result)

    resp = client.get("/api/v1/admin/tags")

    assert resp.status_code == 200
    assert resp.json() == [{"name": "営業部", "description": "営業・提案担当"}]


def test_create_tag_returns_201(client: TestClient, mock_db: AsyncMock) -> None:
    """POST /admin/tags が 201 を返し、作成したタグを返す"""
    not_found = MagicMock()
    not_found.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=not_found)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.add = MagicMock()

    resp = client.post("/api/v1/admin/tags", json={"name": "人事部", "description": "採用担当"})

    assert resp.status_code == 201
    assert resp.json()["name"] == "人事部"


def test_create_tag_conflict_returns_409(client: TestClient, mock_db: AsyncMock) -> None:
    """既存名で POST すると 409"""
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = DepartmentTag(name="営業部", description=None)
    mock_db.execute = AsyncMock(return_value=existing_result)

    resp = client.post("/api/v1/admin/tags", json={"name": "営業部"})

    assert resp.status_code == 409


def test_update_tag_not_found_returns_404(client: TestClient, mock_db: AsyncMock) -> None:
    """存在しないタグを PATCH すると 404"""
    not_found = MagicMock()
    not_found.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=not_found)

    resp = client.patch("/api/v1/admin/tags/nonexistent", json={"description": "新説明"})

    assert resp.status_code == 404


def test_delete_tag_returns_204(client: TestClient, mock_db: AsyncMock) -> None:
    """DELETE /admin/tags/{tag} が 204 を返す"""
    tag = DepartmentTag(name="営業部", description=None)
    tag_result = MagicMock()
    tag_result.scalar_one_or_none.return_value = tag
    user_result = MagicMock()
    user_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(side_effect=[tag_result, user_result])
    mock_db.commit = AsyncMock()

    resp = client.delete("/api/v1/admin/tags/%E5%96%B6%E6%A5%AD%E9%83%A8")  # URL encode "営業部"

    assert resp.status_code == 204
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
pytest tests/unit/test_admin_tags.py -v
```

期待: `ImportError` または `404` 系エラーで全件 FAIL（実装前なので）

- [ ] **Step 3: `src/models/task_web.py` の TagRenameRequest を置換**

403 行目付近の以下のブロックを:

```python
# --- Admin Tag ---


class TagRenameRequest(BaseModel):
    new_name: str = Field(min_length=1, max_length=50)
```

以下に置き換える:

```python
# --- Admin Tag ---


class DepartmentTagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=200)


class DepartmentTagUpdate(BaseModel):
    new_name: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = None


class DepartmentTagResponse(BaseModel):
    model_config = {"from_attributes": True}

    name: str
    description: str | None = None
```

- [ ] **Step 4: `src/api/routers/admin.py` のインポートと全タグエンドポイントを更新**

ファイル先頭の import を以下に変更（`TagRenameRequest` を削除し新モデルを追加）:

```python
from src.db.models import DepartmentTag, UserProfile
from src.models.task_web import (
    AdminUserCreate,
    AdminUserResponse,
    AdminUserUpdate,
    DepartmentTagCreate,
    DepartmentTagResponse,
    DepartmentTagUpdate,
)
```

ファイル末尾の `# --- タグ管理 ---` セクション全体を以下に置き換える:

```python
# --- タグ管理 ---


@router.get("/tags", response_model=list[DepartmentTagResponse])
async def list_tags(db: DbDep, _: AdminDep) -> list[DepartmentTagResponse]:
    result = await db.execute(select(DepartmentTag).order_by(DepartmentTag.name))
    return [DepartmentTagResponse.model_validate(t) for t in result.scalars().all()]


@router.post("/tags", response_model=DepartmentTagResponse, status_code=status.HTTP_201_CREATED)
async def create_tag(body: DepartmentTagCreate, db: DbDep, _: AdminDep) -> DepartmentTagResponse:
    existing = await db.execute(select(DepartmentTag).where(DepartmentTag.name == body.name))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="タグが既に存在します")
    tag = DepartmentTag(name=body.name, description=body.description)
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return DepartmentTagResponse.model_validate(tag)


@router.patch("/tags/{tag}", response_model=DepartmentTagResponse)
async def update_tag(tag: str, body: DepartmentTagUpdate, db: DbDep, _: AdminDep) -> DepartmentTagResponse:
    result = await db.execute(select(DepartmentTag).where(DepartmentTag.name == tag))
    dept_tag = result.scalar_one_or_none()
    if dept_tag is None:
        raise HTTPException(status_code=404, detail="タグが見つかりません")

    new_name = body.new_name if body.new_name is not None else tag

    if new_name != tag:
        # タグ名変更: 全ユーザーの department_tags 配列も更新
        user_result = await db.execute(
            select(UserProfile).where(UserProfile.department_tags.op("@>")(pg_array([tag])))
        )
        for user in user_result.scalars().all():
            user.department_tags = [
                new_name if t == tag else t for t in (user.department_tags or [])
            ]
        # PK 変更のため DELETE + INSERT
        await db.delete(dept_tag)
        await db.flush()
        dept_tag = DepartmentTag(name=new_name, description=body.description)
        db.add(dept_tag)
    else:
        dept_tag.description = body.description

    await db.commit()
    # commit 後に re-fetch（expire 対策）
    refreshed = await db.execute(select(DepartmentTag).where(DepartmentTag.name == new_name))
    return DepartmentTagResponse.model_validate(refreshed.scalar_one())


@router.delete("/tags/{tag}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(tag: str, db: DbDep, _: AdminDep) -> None:
    # department_tags テーブルから削除
    tag_result = await db.execute(select(DepartmentTag).where(DepartmentTag.name == tag))
    dept_tag = tag_result.scalar_one_or_none()
    if dept_tag is not None:
        await db.delete(dept_tag)

    # 全ユーザーの department_tags 配列からも削除
    user_result = await db.execute(
        select(UserProfile).where(UserProfile.department_tags.op("@>")(pg_array([tag])))
    )
    for user in user_result.scalars().all():
        user.department_tags = [t for t in (user.department_tags or []) if t != tag]

    await db.commit()
```

- [ ] **Step 5: テストを実行して全件 PASS を確認**

```bash
pytest tests/unit/test_admin_tags.py -v
```

期待:
```
test_list_tags_returns_tag_objects PASSED
test_create_tag_returns_201 PASSED
test_create_tag_conflict_returns_409 PASSED
test_update_tag_not_found_returns_404 PASSED
test_delete_tag_returns_204 PASSED
5 passed
```

- [ ] **Step 6: 全テストスイートを実行してリグレッションがないことを確認**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -20
```

期待: 全 250+ tests passed（新規 5 件追加で合計 250 passed）

- [ ] **Step 7: コミット**

```bash
git add src/models/task_web.py src/api/routers/admin.py tests/unit/test_admin_tags.py
git commit -m "feat: department tag CRUD with description (Issue #1)"
```

---

## Task 3: フロントエンド hooks 更新

**Files:**
- Modify: `frontend/src/hooks/useAdminTags.ts`

---

- [ ] **Step 1: `useAdminTags.ts` を完全に書き替える**

`frontend/src/hooks/useAdminTags.ts` の内容を以下に置き換える:

```typescript
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'

export interface DepartmentTagResponse {
  name: string
  description: string | null
}

export function useAdminTags() {
  return useQuery<DepartmentTagResponse[]>({
    queryKey: ['admin-tags'],
    queryFn: async () => {
      const { data } = await api.get<DepartmentTagResponse[]>('/admin/tags')
      return data
    },
  })
}

export function useCreateTag() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: { name: string; description: string | null }) => {
      const { data } = await api.post<DepartmentTagResponse>('/admin/tags', body)
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-tags'] })
    },
  })
}

export function useUpdateTag() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      tag,
      newName,
      description,
    }: {
      tag: string
      newName?: string
      description: string | null
    }) => {
      await api.patch(`/admin/tags/${encodeURIComponent(tag)}`, {
        new_name: newName ?? null,
        description,
      })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-tags'] })
      qc.invalidateQueries({ queryKey: ['admin-users'] })
    },
  })
}

export function useDeleteTag() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (tag: string) => {
      await api.delete(`/admin/tags/${encodeURIComponent(tag)}`)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-tags'] })
      qc.invalidateQueries({ queryKey: ['admin-users'] })
    },
  })
}
```

> **注意:** `useRenameTag` を `useUpdateTag` に置き換える。`OrgSettings.tsx` でも参照を変更する（Task 4 で行う）。

- [ ] **Step 2: TypeScript 型チェックを実行**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```

期待: `OrgSettings.tsx` が `useRenameTag` を参照しているため **エラーが出る**（Task 4 で修正する）

- [ ] **Step 3: コミット（TypeScript エラーは Task 4 で修正する旨をメッセージに記載）**

```bash
git add frontend/src/hooks/useAdminTags.ts
git commit -m "feat: update useAdminTags hooks - add useCreateTag/useUpdateTag, DepartmentTagResponse type"
```

---

## Task 4: フロントエンド OrgSettings.tsx 更新

**Files:**
- Modify: `frontend/src/pages/Admin/OrgSettings.tsx`

---

- [ ] **Step 1: `OrgSettings.tsx` を完全に書き替える**

`frontend/src/pages/Admin/OrgSettings.tsx` の内容を以下に置き換える:

```typescript
import { useState } from 'react'
import {
  Button,
  Card,
  Input,
  message,
  Modal,
  Popconfirm,
  Space,
  Table,
  Typography,
} from 'antd'
import { DeleteOutlined, EditOutlined, PlusOutlined } from '@ant-design/icons'
import {
  DepartmentTagResponse,
  useAdminTags,
  useCreateTag,
  useDeleteTag,
  useUpdateTag,
} from '../../hooks/useAdminTags'
import { useAdminUsers } from '../../hooks/useAdminUsers'

export default function OrgSettings() {
  const { data: tags = [], isLoading } = useAdminTags()
  const { data: users = [] } = useAdminUsers()
  const createTag = useCreateTag()
  const updateTag = useUpdateTag()
  const deleteTag = useDeleteTag()

  // 編集モーダル
  const [editingTag, setEditingTag] = useState<DepartmentTagResponse | null>(null)
  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')

  // 新規追加モーダル
  const [createOpen, setCreateOpen] = useState(false)
  const [newName, setNewName] = useState('')
  const [newDescription, setNewDescription] = useState('')

  const userCountByTag = Object.fromEntries(
    tags.map((t) => [t.name, users.filter((u) => u.department_tags.includes(t.name)).length]),
  )

  const handleUpdate = async () => {
    if (!editingTag || !editName.trim()) return
    try {
      await updateTag.mutateAsync({
        tag: editingTag.name,
        newName: editName.trim() !== editingTag.name ? editName.trim() : undefined,
        description: editDescription.trim() || null,
      })
      void message.success('タグを更新しました')
      setEditingTag(null)
    } catch {
      void message.error('更新に失敗しました')
    }
  }

  const handleCreate = async () => {
    if (!newName.trim()) return
    try {
      await createTag.mutateAsync({
        name: newName.trim(),
        description: newDescription.trim() || null,
      })
      void message.success(`"${newName.trim()}" を追加しました`)
      setCreateOpen(false)
      setNewName('')
      setNewDescription('')
    } catch {
      void message.error('タグの追加に失敗しました')
    }
  }

  const columns = [
    {
      title: '部門タグ',
      dataIndex: 'name',
      key: 'name',
      render: (name: string) => <strong>{name}</strong>,
    },
    {
      title: '説明',
      dataIndex: 'description',
      key: 'description',
      render: (desc: string | null) =>
        desc ? desc : <Typography.Text type="secondary">—</Typography.Text>,
    },
    {
      title: '対象ユーザー数',
      key: 'count',
      render: (_: unknown, record: DepartmentTagResponse) =>
        `${userCountByTag[record.name] ?? 0} 名`,
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: DepartmentTagResponse) => (
        <Space>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => {
              setEditingTag(record)
              setEditName(record.name)
              setEditDescription(record.description ?? '')
            }}
          >
            編集
          </Button>
          <Popconfirm
            title={`"${record.name}" を削除しますか？`}
            description={`${userCountByTag[record.name] ?? 0} 名のユーザーからこのタグが削除されます。`}
            onConfirm={() => void deleteTag.mutateAsync(record.name)}
            okText="削除"
            cancelText="キャンセル"
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              削除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <Typography.Title level={5} style={{ margin: 0 }}>
            部門タグ一元管理
          </Typography.Title>
          <Typography.Text type="secondary">
            システム内で使用する部門タグを管理します。タグを追加して各ユーザーに割り当ててください。
          </Typography.Text>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          タグを追加
        </Button>
      </div>

      <Card>
        <Table
          rowKey="name"
          loading={isLoading}
          dataSource={tags}
          columns={columns}
          pagination={false}
          size="small"
        />
      </Card>

      {/* 編集モーダル */}
      <Modal
        title="タグを編集"
        open={!!editingTag}
        onOk={() => void handleUpdate()}
        onCancel={() => setEditingTag(null)}
        confirmLoading={updateTag.isPending}
        okText="保存"
        cancelText="キャンセル"
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <Typography.Text strong>タグ名</Typography.Text>
            <Input
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              onPressEnter={() => void handleUpdate()}
              placeholder="タグ名"
              style={{ marginTop: 4 }}
            />
          </div>
          <div>
            <Typography.Text strong>説明</Typography.Text>
            <Input.TextArea
              value={editDescription}
              onChange={(e) => setEditDescription(e.target.value)}
              placeholder="このタグの説明（省略可）"
              rows={2}
              style={{ marginTop: 4 }}
            />
          </div>
        </Space>
      </Modal>

      {/* 新規追加モーダル */}
      <Modal
        title="タグを追加"
        open={createOpen}
        onOk={() => void handleCreate()}
        onCancel={() => {
          setCreateOpen(false)
          setNewName('')
          setNewDescription('')
        }}
        confirmLoading={createTag.isPending}
        okText="追加"
        cancelText="キャンセル"
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <Typography.Text strong>タグ名 *</Typography.Text>
            <Input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onPressEnter={() => void handleCreate()}
              placeholder="例: 営業部"
              style={{ marginTop: 4 }}
            />
          </div>
          <div>
            <Typography.Text strong>説明</Typography.Text>
            <Input.TextArea
              value={newDescription}
              onChange={(e) => setNewDescription(e.target.value)}
              placeholder="このタグの説明（省略可）"
              rows={2}
              style={{ marginTop: 4 }}
            />
          </div>
        </Space>
      </Modal>
    </Space>
  )
}
```

- [ ] **Step 2: TypeScript 型チェックを実行してエラーがないことを確認**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```

期待: エラーなし（0 errors）

- [ ] **Step 3: 全バックエンドテストを実行してリグレッションがないことを確認**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -5
```

期待: `250 passed`（以上）

- [ ] **Step 4: コミット**

```bash
git add frontend/src/pages/Admin/OrgSettings.tsx
git commit -m "feat: org settings - add tag creation modal and description column (Issue #1)"
```

---

## 実装後の動作確認チェックリスト

ローカルで `uvicorn` + `npm run dev` を起動後に確認:

1. 管理設定 → 組織設定 → 部門タグ一覧に **説明** 列が表示される
2. 「タグを追加」ボタンをクリック → モーダルでタグ名と説明を入力 → 「追加」→ 一覧に反映される
3. 既存タグの「編集」→ タグ名変更 + 説明変更 → 「保存」→ 一覧に反映される
4. 「削除」→ 確認ダイアログ → 削除実行 → 一覧から消える
5. 同名タグを「タグを追加」しようとすると失敗メッセージが表示される（409）
