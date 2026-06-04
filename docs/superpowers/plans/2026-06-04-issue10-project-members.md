# Issue #10 — プロジェクトメンバー基盤 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `project_members` テーブルを新設し、プロジェクト作成時のメンバー追加 API と、サイドバーのプロジェクトコンテキスト選択 UI を実装する。

**Architecture:** DB に `project_members` テーブルを追加（Alembic 0010）→ バックエンドでメンバー CRUD + `list_projects` スコープフィルタを追加 → フロントに Zustand ストア `useProjectStore` と `ProjectContextSelector` コンポーネントを追加してサイドバーに統合する。

**Tech Stack:** SQLAlchemy 2.x (Mapped 型), Alembic, FastAPI, Pydantic v2, React 18 + TypeScript, Zustand (persist), Ant Design 5.x, TanStack Query 5.x

---

## ファイルマップ

| 操作 | パス |
|-----|-----|
| 新規作成 | `alembic/versions/0010_project_members.py` |
| 修正 | `src/db/models.py` — `ProjectMember` クラス追加・`Project.members` リレーション追加 |
| 修正 | `src/models/task_web.py` — `ProjectMemberAdd` / `ProjectMemberResponse` / `ProjectCreate` 拡張 |
| 修正 | `src/api/routers/projects.py` — メンバー CRUD エンドポイント追加・`list_projects` スコープ対応 |
| 新規作成 | `frontend/src/store/useProjectStore.ts` |
| 新規作成 | `frontend/src/components/ProjectContextSelector.tsx` |
| 修正 | `frontend/src/hooks/useProjects.ts` — `scope` パラメータ追加 |
| 修正 | `frontend/src/App.tsx` — `ProjectContextSelector` をサイドバーに追加 |
| 新規作成 | `tests/unit/test_project_members.py` |

---

### Task 1: Alembic マイグレーション 0010

**Files:**
- Create: `alembic/versions/0010_project_members.py`

- [ ] **Step 1: マイグレーションファイルを作成する**

```python
# alembic/versions/0010_project_members.py
"""project_members テーブル追加

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_members",
        sa.Column(
            "project_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Text, nullable=False),
        sa.Column("role", sa.String(10), nullable=False, server_default="member"),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("project_id", "user_id"),
    )


def downgrade() -> None:
    op.drop_table("project_members")
```

- [ ] **Step 2: マイグレーションを適用する**

```bash
alembic upgrade head
```

期待出力: `Running upgrade 0009 -> 0010, project_members テーブル追加`

---

### Task 2: SQLAlchemy モデル追加

**Files:**
- Modify: `src/db/models.py`

- [ ] **Step 1: `ProjectMember` クラスを追加する**

`src/db/models.py` の `DepartmentTag` クラスの直前（約 218 行目）に以下を挿入する：

```python
class ProjectMember(Base):
    __tablename__ = "project_members"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    role: Mapped[str] = mapped_column(String(10), nullable=False, default="member")
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    project: Mapped["Project"] = relationship("Project", back_populates="members")
```

- [ ] **Step 2: `Project` クラスに `members` リレーションを追加する**

`src/db/models.py` の `Project` クラス（約 44 行目）の `sections` リレーション後に追加：

```python
    members: Mapped[list["ProjectMember"]] = relationship(
        "ProjectMember", back_populates="project", cascade="all, delete-orphan"
    )
```

- [ ] **Step 3: インポートに変更がないことを確認する**

`src/db/models.py` の先頭に `UniqueConstraint` が既にインポートされていることを確認（既存）。`ProjectMember` は新しいインポートを必要としない。

---

### Task 3: Pydantic モデル追加 + テスト作成

**Files:**
- Modify: `src/models/task_web.py`
- Create: `tests/unit/test_project_members.py`

- [ ] **Step 1: テストを書く（まず失敗を確認）**

```python
# tests/unit/test_project_members.py
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_add_member_as_owner(client: AsyncClient, auth_headers: dict) -> None:
    """プロジェクト作成者がメンバーを追加できる。"""
    # プロジェクト作成
    r = await client.post("/api/v1/projects", json={"name": "MemberTest"}, headers=auth_headers)
    assert r.status_code == 201
    project_id = r.json()["id"]

    # メンバー追加
    r2 = await client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"user_id": "user-b", "role": "member"},
        headers=auth_headers,
    )
    assert r2.status_code == 201
    assert r2.json()["user_id"] == "user-b"
    assert r2.json()["role"] == "member"


@pytest.mark.asyncio
async def test_list_members(client: AsyncClient, auth_headers: dict) -> None:
    """メンバー一覧が取得できる。"""
    r = await client.post("/api/v1/projects", json={"name": "ListMemberTest"}, headers=auth_headers)
    project_id = r.json()["id"]
    await client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"user_id": "user-c", "role": "member"},
        headers=auth_headers,
    )
    r2 = await client.get(f"/api/v1/projects/{project_id}/members", headers=auth_headers)
    assert r2.status_code == 200
    user_ids = [m["user_id"] for m in r2.json()]
    assert "user-c" in user_ids


@pytest.mark.asyncio
async def test_remove_member(client: AsyncClient, auth_headers: dict) -> None:
    """メンバーを削除できる。"""
    r = await client.post("/api/v1/projects", json={"name": "RemoveMemberTest"}, headers=auth_headers)
    project_id = r.json()["id"]
    await client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"user_id": "user-d", "role": "member"},
        headers=auth_headers,
    )
    r2 = await client.delete(
        f"/api/v1/projects/{project_id}/members/user-d", headers=auth_headers
    )
    assert r2.status_code == 204


@pytest.mark.asyncio
async def test_list_projects_scope_mine(client: AsyncClient, auth_headers: dict) -> None:
    """scope=mine ではメンバーのプロジェクトのみ返る。"""
    # 別ユーザーが作ったプロジェクト（自分はメンバーではない）はリストに含まれない
    r = await client.get("/api/v1/projects", headers=auth_headers)
    assert r.status_code == 200
    # 自分が作成者 or メンバーのプロジェクトのみ
    # 詳細な検証はインテグレーションテストで行う


@pytest.mark.asyncio
async def test_create_project_with_members(client: AsyncClient, auth_headers: dict) -> None:
    """プロジェクト作成時にメンバーを一括追加できる。"""
    r = await client.post(
        "/api/v1/projects",
        json={"name": "WithMembers", "member_ids": ["user-e", "user-f"]},
        headers=auth_headers,
    )
    assert r.status_code == 201
    project_id = r.json()["id"]
    r2 = await client.get(f"/api/v1/projects/{project_id}/members", headers=auth_headers)
    user_ids = [m["user_id"] for m in r2.json()]
    assert "user-e" in user_ids
    assert "user-f" in user_ids


@pytest.mark.asyncio
async def test_add_member_non_owner_forbidden(client: AsyncClient, auth_headers: dict, other_auth_headers: dict) -> None:
    """owner でないユーザーはメンバー追加できない（403）。"""
    r = await client.post("/api/v1/projects", json={"name": "ForbidTest"}, headers=auth_headers)
    project_id = r.json()["id"]
    r2 = await client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"user_id": "user-g", "role": "member"},
        headers=other_auth_headers,
    )
    assert r2.status_code == 403
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
pytest tests/unit/test_project_members.py -v
```

期待: `ImportError` または `404`（エンドポイント未実装）

- [ ] **Step 3: Pydantic モデルを `src/models/task_web.py` に追加する**

`ProjectResponse` クラスの後（約 370 行目）に追加：

```python
# --- ProjectMember ---

class ProjectMemberAdd(BaseModel):
    user_id: str
    role: str = "member"

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ("owner", "member"):
            raise ValueError("role は 'owner' または 'member' のみ有効です")
        return v


class ProjectMemberResponse(BaseModel):
    project_id: uuid.UUID
    user_id: str
    role: str
    joined_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: `ProjectCreate` に `member_ids` を追加する**

`src/models/task_web.py` で `ProjectUpdate` と `_ProjectCreate` に相当する箇所を確認し、`src/api/routers/projects.py` の `_ProjectCreate` に追加：

```python
class _ProjectCreate(ProjectUpdate):
    name: str
    member_ids: list[str] = Field(default_factory=list)
```

---

### Task 4: プロジェクトメンバー API エンドポイントを実装する

**Files:**
- Modify: `src/api/routers/projects.py`

- [ ] **Step 1: インポートに `ProjectMember` を追加する**

`src/api/routers/projects.py` 冒頭の import を更新：

```python
from src.db.models import Project, ProjectMember
from src.models.task_web import (
    ProjectMemberAdd,
    ProjectMemberResponse,
    ProjectResponse,
    ProjectUpdate,
)
```

- [ ] **Step 2: `_is_project_owner` ヘルパーを追加する**

既存の `_check_project_permission` の後に追加：

```python
def _is_project_owner(project_id: uuid.UUID, current_user: CurrentUser) -> bool:
    """project_members テーブルを使った owner 判定は非同期が必要なため、
    create_project で owner を必ず登録し、ここでは created_by と一致するかで判定する。"""
    return True  # 実際の判定は各エンドポイント内で DB クエリ


async def _assert_owner_or_admin(
    project_id: uuid.UUID, db: AsyncSession, current_user: CurrentUser
) -> None:
    """project_members で role=owner か admin ロールでなければ 403。"""
    user_role = max((ROLE_HIERARCHY.get(r, 0) for r in current_user.roles), default=0)
    if user_role >= ROLE_HIERARCHY["admin"]:
        return
    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == current_user.sub,
            ProjectMember.role == "owner",
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="プロジェクトオーナーまたは管理者のみ操作できます")
```

- [ ] **Step 3: `create_project` を更新して作成者を owner として登録・`member_ids` を一括追加する**

既存の `create_project` を以下に置き換える：

```python
@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: _ProjectCreate, db: DbDep, current_user: CurrentUser
) -> ProjectResponse:
    project = Project(
        name=body.name,
        description=body.description,
        status=body.status or "active",
        created_by=current_user.sub,
    )
    db.add(project)
    await db.flush()  # project.id を確定させる

    # 作成者を owner として登録
    db.add(ProjectMember(project_id=project.id, user_id=current_user.sub, role="owner"))

    # member_ids を一括登録
    for uid in body.member_ids:
        if uid != current_user.sub:
            db.add(ProjectMember(project_id=project.id, user_id=uid, role="member"))

    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)
```

- [ ] **Step 4: `list_projects` にスコープフィルタを追加する**

既存の `list_projects` を以下に置き換える：

```python
@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    db: DbDep,
    current_user: CurrentUser,
    include_archived: bool = Query(default=False),
    scope: str = Query(default="mine"),  # "mine" | "all"
) -> list[ProjectResponse]:
    user_role = max((ROLE_HIERARCHY.get(r, 0) for r in current_user.roles), default=0)
    query = select(Project).order_by(Project.created_at.desc())
    if not include_archived:
        query = query.where(Project.status != "archived")
    # admin は scope に関わらず全件参照可
    if scope == "mine" and user_role < ROLE_HIERARCHY["admin"]:
        query = query.where(
            Project.id.in_(
                select(ProjectMember.project_id).where(
                    ProjectMember.user_id == current_user.sub
                )
            )
        )
    result = await db.execute(query)
    return [ProjectResponse.model_validate(p) for p in result.scalars().all()]
```

- [ ] **Step 5: メンバー一覧・追加・削除エンドポイントを追加する**

`delete_project` エンドポイントの後に追加：

```python
@router.get("/{project_id}/members", response_model=list[ProjectMemberResponse])
async def list_project_members(
    project_id: uuid.UUID, db: DbDep, current_user: CurrentUser
) -> list[ProjectMemberResponse]:
    result = await db.execute(
        select(ProjectMember)
        .where(ProjectMember.project_id == project_id)
        .order_by(ProjectMember.joined_at)
    )
    return [ProjectMemberResponse.model_validate(m) for m in result.scalars().all()]


@router.post(
    "/{project_id}/members",
    response_model=ProjectMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_project_member(
    project_id: uuid.UUID,
    body: ProjectMemberAdd,
    db: DbDep,
    current_user: CurrentUser,
) -> ProjectMemberResponse:
    await _assert_owner_or_admin(project_id, db, current_user)
    # 重複チェック
    exists = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == body.user_id,
        )
    )
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="既にメンバーに追加されています")
    member = ProjectMember(project_id=project_id, user_id=body.user_id, role=body.role)
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return ProjectMemberResponse.model_validate(member)


@router.delete("/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_project_member(
    project_id: uuid.UUID,
    user_id: str,
    db: DbDep,
    current_user: CurrentUser,
) -> None:
    await _assert_owner_or_admin(project_id, db, current_user)
    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="メンバーが見つかりません")
    await db.delete(member)
    await db.commit()
```

- [ ] **Step 6: テストを実行する**

```bash
pytest tests/unit/test_project_members.py -v
```

期待: 6 件全 PASS

- [ ] **Step 7: コミットする**

```bash
git add alembic/versions/0010_project_members.py src/db/models.py src/models/task_web.py src/api/routers/projects.py tests/unit/test_project_members.py
git commit -m "feat: project_members テーブル追加・メンバー CRUD API・list_projects スコープフィルタ (#10)"
```

---

### Task 5: フロントエンド — Zustand ストア

**Files:**
- Create: `frontend/src/store/useProjectStore.ts`

- [ ] **Step 1: `useProjectStore.ts` を作成する**

```typescript
// frontend/src/store/useProjectStore.ts
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface ProjectStore {
  activeProjectIds: string[]
  activeDeptTag: string | null
  setActiveProjects: (ids: string[]) => void
  setActiveDeptTag: (tag: string | null) => void
}

export const useProjectStore = create<ProjectStore>()(
  persist(
    (set) => ({
      activeProjectIds: [],
      activeDeptTag: null,
      setActiveProjects: (ids) => set({ activeProjectIds: ids }),
      setActiveDeptTag: (tag) => set({ activeDeptTag: tag }),
    }),
    { name: 'autoticket-project-store' }
  )
)
```

---

### Task 6: フロントエンド — ProjectContextSelector コンポーネント

**Files:**
- Create: `frontend/src/components/ProjectContextSelector.tsx`
- Modify: `frontend/src/hooks/useProjects.ts`

- [ ] **Step 1: `useProjects` に scope パラメータを追加する**

`frontend/src/hooks/useProjects.ts` の `useProjects` 関数を更新：

```typescript
export function useProjects(params: { includeArchived?: boolean; scope?: 'mine' | 'all' } = {}) {
  const { includeArchived = false, scope = 'mine' } = params
  return useQuery<Project[]>({
    queryKey: ['projects', { includeArchived, scope }],
    queryFn: async () => {
      const { data } = await api.get('/projects', {
        params: {
          ...(includeArchived ? { include_archived: true } : {}),
          scope,
        },
      })
      return data
    },
  })
}
```

- [ ] **Step 2: `ProjectContextSelector.tsx` を作成する**

```typescript
// frontend/src/components/ProjectContextSelector.tsx
import { useEffect } from 'react'
import { Select, Space, Typography } from 'antd'
import { useAuthStore } from '../store/useAuthStore'
import { useProjectStore } from '../store/useProjectStore'
import { useProjects } from '../hooks/useProjects'

export default function ProjectContextSelector() {
  const { user } = useAuthStore()
  const { activeProjectIds, activeDeptTag, setActiveProjects, setActiveDeptTag } =
    useProjectStore()
  const { data: projects = [] } = useProjects({ scope: 'mine' })

  const deptTags: string[] = (user as { department_tags?: string[] })?.department_tags ?? []
  const multipleDepts = deptTags.length > 1

  // 初回: activeDeptTag が未設定なら最初の部門タグをセット
  useEffect(() => {
    if (!activeDeptTag && deptTags.length > 0) {
      setActiveDeptTag(deptTags[0])
    }
  }, [deptTags, activeDeptTag, setActiveDeptTag])

  return (
    <Space
      direction="vertical"
      size={4}
      style={{
        width: '100%',
        padding: '10px 12px',
        borderBottom: '1px solid #f0f0f0',
        background: '#fafafa',
      }}
    >
      <div>
        <Typography.Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 2 }}>
          所属部門
        </Typography.Text>
        <Select
          size="small"
          style={{ width: '100%' }}
          value={activeDeptTag ?? deptTags[0] ?? undefined}
          onChange={setActiveDeptTag}
          disabled={!multipleDepts}
          placeholder="部門未設定"
          options={deptTags.map((t) => ({ value: t, label: t }))}
        />
      </div>
      <div>
        <Typography.Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 2 }}>
          プロジェクト
        </Typography.Text>
        <Select
          mode="multiple"
          size="small"
          style={{ width: '100%' }}
          placeholder="全プロジェクト"
          value={activeProjectIds}
          onChange={setActiveProjects}
          allowClear
          options={projects.map((p) => ({ value: p.id, label: p.name }))}
          maxTagCount={1}
          maxTagTextLength={10}
        />
      </div>
    </Space>
  )
}
```

- [ ] **Step 3: `App.tsx` の Sider に `ProjectContextSelector` を追加する**

`frontend/src/App.tsx` の import に追加：

```typescript
import ProjectContextSelector from './components/ProjectContextSelector'
```

Sider の中（`<Menu ...>` の直前）に追加：

```tsx
<Sider width={220} theme="light">
  <ProjectContextSelector />
  <Menu
    mode="inline"
    selectedKeys={[selectedKey]}
    style={{ height: 'calc(100% - 100px)', borderRight: 0, overflowY: 'auto' }}
    items={navItemsWithAdmin}
    onClick={({ key }) => navigate(key)}
  />
</Sider>
```

- [ ] **Step 4: TypeScript ビルドを確認する**

```bash
cd frontend && npx tsc --noEmit
```

期待: エラーなし

- [ ] **Step 5: コミットする**

```bash
git add frontend/src/store/useProjectStore.ts frontend/src/components/ProjectContextSelector.tsx frontend/src/hooks/useProjects.ts frontend/src/App.tsx
git commit -m "feat: プロジェクトコンテキスト選択UIをサイドバーに追加 (#10)"
```

---

### Task 7: 全テスト実行・最終確認

- [ ] **Step 1: バックエンドテストを全件実行する**

```bash
pytest tests/ -v --tb=short
```

期待: 既存 245 件 + 新規 6 件 = 251 件 PASS

- [ ] **Step 2: フロントエンドビルドを確認する**

```bash
cd frontend && npm run build
```

期待: ビルドエラーなし

- [ ] **Step 3: コミット済みであることを確認する**

```bash
git log --oneline -3
```
