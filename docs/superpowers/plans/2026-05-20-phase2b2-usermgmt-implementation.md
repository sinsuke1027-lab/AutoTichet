# Web App Phase 2B-2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 部門タグ方式のユーザー管理・ロールベース閲覧制御・JWT-first/DB-fallback ハイブリッド認証を実装し、F-07 個人 ToDo・F-04 二重登録防止・F-11 スケジュール D&D を追加する。

**Architecture:** 既存の `list_tasks` に可視性フィルタをインライン追加（Approach A）。新規 Dependency なし。`UserProfile.department_tags`（JSONB）と `auth.py` 拡張で完結。バックエンド先行で実装し、フロントエンドは後半でまとめて実装する。

**Tech Stack:** FastAPI + SQLAlchemy 2.x (asyncpg) + Alembic + PostgreSQL JSONB / React 18 + TypeScript strict + Ant Design 5 + @dnd-kit/core + TanStack Query 5

---

## ファイル構成

### 新規作成
```
alembic/versions/0003_add_start_date.py          ← Phase 2B-1 で漏れた migration
alembic/versions/0004_add_department_tags.py
src/api/routers/admin.py
tests/unit/test_admin_router.py
tests/unit/test_visibility.py
tests/unit/test_similar_tasks.py
frontend/src/pages/Admin/Users.tsx
frontend/src/hooks/useAdminUsers.ts
frontend/src/hooks/useSimilarTasks.ts
```

### 変更
```
src/db/models.py              ← UserProfile に department_tags: JSONB 追加
src/api/auth.py               ← ROLE_HIERARCHY 公開・TokenPayload に department_tags・DB fallback
src/models/task_web.py        ← AdminUserCreate/Update/Response・SimilarTaskResponse 追加
src/api/routers/tasks_crud.py ← visibility フィルタ・my_tasks_only・/similar エンドポイント
src/api/main.py               ← admin ルーター登録
frontend/src/lib/api.ts       ← AdminUser・SimilarTask 型・UserProfile に department_tags
frontend/src/App.tsx          ← /admin/users ルート・サイドバー（admin のみ）
frontend/src/pages/Tasks/index.tsx  ← ToDo スイッチ・visibility Select・類似タスク警告
frontend/src/pages/Schedule/index.tsx ← 週次 D&D グリッドに刷新
```

---

## Task 1: Alembic 0003 — start_date migration（補完）

Phase 2B-1 で ORM は更新済みだがマイグレーションファイルが未作成。

**Files:**
- Create: `alembic/versions/0003_add_start_date.py`

- [ ] **Step 1: マイグレーションファイルを作成**

```python
# alembic/versions/0003_add_start_date.py
"""add start_date to tasks

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("start_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "start_date")
```

- [ ] **Step 2: マイグレーション適用を確認**

```bash
cd "C:/Users/shinsuke-imanaka/OneDrive - 株式会社デジタルフォルン/デスクトップ/研修・各スキル/Google Antigravity Apps/AutoTicket"
alembic upgrade 0003
```

Expected: `Running upgrade 0002 -> 0003, add start_date to tasks`

- [ ] **Step 3: コミット**

```bash
git add alembic/versions/0003_add_start_date.py
git commit -m "feat: Alembic 0003 — tasks.start_date migration（Phase 2B-1 補完）"
```

---

## Task 2: Alembic 0004 + ORM — department_tags JSONB

**Files:**
- Create: `alembic/versions/0004_add_department_tags.py`
- Modify: `src/db/models.py`

- [ ] **Step 1: マイグレーションファイルを作成**

```python
# alembic/versions/0004_add_department_tags.py
"""add department_tags to user_profiles

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column(
            "department_tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
    )


def downgrade() -> None:
    op.drop_column("user_profiles", "department_tags")
```

- [ ] **Step 2: ORM モデルに department_tags を追加**

`src/db/models.py` の先頭 import に追加：
```python
from sqlalchemy.dialects.postgresql import JSONB
```

`UserProfile` クラスの `skills` 行の直後に追加：
```python
    department_tags: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
```

- [ ] **Step 3: マイグレーション適用**

```bash
alembic upgrade 0004
```

Expected: `Running upgrade 0003 -> 0004, add department_tags to user_profiles`

- [ ] **Step 4: コミット**

```bash
git add alembic/versions/0004_add_department_tags.py src/db/models.py
git commit -m "feat: Alembic 0004 — user_profiles.department_tags JSONB"
```

---

## Task 3: Pydantic モデル追加（task_web.py）

**Files:**
- Modify: `src/models/task_web.py`

- [ ] **Step 1: ファイル末尾に Admin/Similar モデルを追加**

`src/models/task_web.py` の末尾（`RescheduleResponse` の後）に追記：

```python
# --- Admin User ---


class AdminUserCreate(BaseModel):
    user_id: str
    display_name: str
    email: str | None = None
    role: str = "member"
    department_tags: list[str] = []
    capacity_hours_per_day: float = 8.0


class AdminUserUpdate(BaseModel):
    display_name: str | None = None
    email: str | None = None
    role: str | None = None
    department_tags: list[str] | None = None
    capacity_hours_per_day: float | None = None


class AdminUserResponse(BaseModel):
    model_config = {"from_attributes": True}

    user_id: str
    display_name: str
    email: str | None = None
    role: str
    department_tags: list[str]
    capacity_hours_per_day: float


# --- Similar Task ---


class SimilarTaskResponse(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    score: float
```

- [ ] **Step 2: pytest で既存テストが壊れていないことを確認**

```bash
pytest tests/unit/test_task_web_models.py -v
```

Expected: 12 passed

- [ ] **Step 3: コミット**

```bash
git add src/models/task_web.py
git commit -m "feat: AdminUser・SimilarTask Pydantic モデル追加"
```

---

## Task 4: auth.py — ハイブリッド認証拡張

**Files:**
- Modify: `src/api/auth.py`

- [ ] **Step 1: `_ROLE_HIERARCHY` を `ROLE_HIERARCHY` に rename し、import を追加**

`src/api/auth.py` 全体を以下に置き換える：

```python
import time
from collections.abc import Callable, Coroutine
from typing import Annotated, Any

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import get_db
from src.models.config import get_settings

_bearer = HTTPBearer(auto_error=False)

ROLE_HIERARCHY: dict[str, int] = {
    "member": 0,
    "leader": 1,
    "manager": 2,
    "admin": 3,
}

_JWKS_TTL = 3600.0
_jwks_cache: dict[str, tuple[dict[str, Any], float]] = {}


class TokenPayload(BaseModel):
    sub: str
    name: str = ""
    email: str = ""
    roles: list[str] = []
    tid: str = ""
    department_tags: list[str] = []
```

Wait - `BaseModel` is not imported. Add import at top:

```python
import time
from collections.abc import Callable, Coroutine
from typing import Annotated, Any

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import get_db
from src.models.config import get_settings

_bearer = HTTPBearer(auto_error=False)

ROLE_HIERARCHY: dict[str, int] = {
    "member": 0,
    "leader": 1,
    "manager": 2,
    "admin": 3,
}

_JWKS_TTL = 3600.0
_jwks_cache: dict[str, tuple[dict[str, Any], float]] = {}


class TokenPayload(BaseModel):
    sub: str
    name: str = ""
    email: str = ""
    roles: list[str] = []
    tid: str = ""
    department_tags: list[str] = []


async def _fetch_jwks(tenant_id: str) -> dict[str, Any]:
    now = time.monotonic()
    cached = _jwks_cache.get(tenant_id)
    if cached is not None and now < cached[1]:
        return cached[0]
    url = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
    _jwks_cache[tenant_id] = (data, now + _JWKS_TTL)
    return data


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
    db: AsyncSession = Depends(get_db),
) -> TokenPayload:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認証が必要です",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    settings = get_settings()
    try:
        jwks = await _fetch_jwks(settings.azure_tenant_id)
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        public_key = next((k for k in jwks["keys"] if k.get("kid") == kid), None)
        if public_key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="署名キーが見つかりません",
            )
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=settings.azure_client_id,
        )
        sub = payload.get("oid", payload.get("sub", ""))

        # DB から UserProfile を取得
        from src.db.models import UserProfile  # avoid circular at module level
        profile_result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == sub)
        )
        profile = profile_result.scalar_one_or_none()

        raw_roles: list[str] = payload.get("roles", [])
        if raw_roles:
            # JWT に roles あり → 本番（Entra ID App Roles）
            roles = raw_roles
        else:
            # JWT に roles なし → 開発環境（DB fallback）
            roles = [profile.role] if profile else ["member"]

        department_tags: list[str] = list(profile.department_tags) if profile else []

        return TokenPayload(
            sub=sub,
            name=payload.get("name", ""),
            email=payload.get("preferred_username", ""),
            roles=roles,
            tid=payload.get("tid", ""),
            department_tags=department_tags,
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"トークン検証失敗: {e}",
        ) from e


def require_role(
    required_role: str,
) -> Callable[[TokenPayload], Coroutine[Any, Any, TokenPayload]]:
    async def _checker(
        current_user: Annotated[TokenPayload, Depends(get_current_user)],
    ) -> TokenPayload:
        user_level = max(
            (ROLE_HIERARCHY.get(r, 0) for r in current_user.roles),
            default=0,
        )
        required_level = ROLE_HIERARCHY.get(required_role, 99)
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="権限が不足しています",
            )
        return current_user

    return _checker


CurrentUser = Annotated[TokenPayload, Depends(get_current_user)]
```

- [ ] **Step 2: 既存テストが通ることを確認**

```bash
pytest tests/unit/test_tasks_crud_router.py tests/unit/test_reschedule.py -v
```

Expected: all passed（dependency_overrides が get_current_user を丸ごと置き換えるため DB 依存は無視される）

- [ ] **Step 3: コミット**

```bash
git add src/api/auth.py
git commit -m "feat: auth — ハイブリッド認証・department_tags・ROLE_HIERARCHY 公開"
```

---

## Task 5: admin.py 新規作成 + main.py 登録

**Files:**
- Create: `src/api/routers/admin.py`
- Modify: `src/api/main.py`

- [ ] **Step 1: admin.py を作成**

```python
# src/api/routers/admin.py
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import TokenPayload, require_role
from src.db.engine import get_db
from src.db.models import UserProfile
from src.models.task_web import AdminUserCreate, AdminUserResponse, AdminUserUpdate

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
AdminDep = Annotated[TokenPayload, Depends(require_role("admin"))]


@router.get("/users", response_model=list[AdminUserResponse])
async def list_admin_users(db: DbDep, _: AdminDep) -> list[AdminUserResponse]:
    result = await db.execute(select(UserProfile))
    return [AdminUserResponse.model_validate(u) for u in result.scalars().all()]


@router.post("/users", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
async def create_admin_user(body: AdminUserCreate, db: DbDep, _: AdminDep) -> AdminUserResponse:
    existing = await db.execute(select(UserProfile).where(UserProfile.user_id == body.user_id))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="ユーザーが既に存在します")
    user = UserProfile(
        user_id=body.user_id,
        display_name=body.display_name,
        email=body.email,
        role=body.role,
        department_tags=body.department_tags,
        capacity_hours_per_day=body.capacity_hours_per_day,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return AdminUserResponse.model_validate(user)


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
async def update_admin_user(
    user_id: str, body: AdminUserUpdate, db: DbDep, _: AdminDep
) -> AdminUserResponse:
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return AdminUserResponse.model_validate(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_admin_user(user_id: str, db: DbDep, _: AdminDep) -> None:
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
    await db.delete(user)
    await db.commit()
```

- [ ] **Step 2: main.py に admin ルーターを登録**

`src/api/main.py` の import ブロック（routers の行）に `admin` を追加：

```python
from src.api.routers import (
    admin,
    dashboard,
    health,
    import_router,
    projects,
    sections,
    task_details,
    tasks,
    tasks_crud,
    users,
)
```

`app.include_router(import_router.router)` の直後に追加：
```python
app.include_router(admin.router)
```

- [ ] **Step 3: サーバー起動確認**

```bash
uvicorn src.api.main:app --reload --port 8000
```

ブラウザで `http://localhost:8000/docs` を開き、`/api/v1/admin/users` が表示されることを確認。

- [ ] **Step 4: コミット**

```bash
git add src/api/routers/admin.py src/api/main.py
git commit -m "feat: admin ルーター — ユーザー CRUD API (/api/v1/admin/users)"
```

---

## Task 6: test_admin_router.py — admin API テスト

**Files:**
- Create: `tests/unit/test_admin_router.py`

- [ ] **Step 1: テストファイルを作成**

```python
# tests/unit/test_admin_router.py
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.api.routers.admin import router
from src.db.engine import get_db

_admin = TokenPayload(sub="admin-1", name="Admin", email="a@a.com", roles=["admin"], tid="t")
_member = TokenPayload(sub="mem-1", name="Mem", email="m@m.com", roles=["member"], tid="t")


@pytest.fixture()
def mock_db() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def admin_client(mock_db: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _admin
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def member_client(mock_db: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _member
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app, raise_server_exceptions=False)


def test_list_users_non_admin_returns_403(member_client: TestClient, mock_db: AsyncMock) -> None:
    resp = member_client.get("/api/v1/admin/users")
    assert resp.status_code == 403


def test_list_users_admin_returns_200(admin_client: TestClient, mock_db: AsyncMock) -> None:
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=result)
    resp = admin_client.get("/api/v1/admin/users")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_user_validates_required_fields(
    admin_client: TestClient, mock_db: AsyncMock
) -> None:
    resp = admin_client.post("/api/v1/admin/users", json={})
    assert resp.status_code == 422


def test_delete_nonexistent_user_returns_404(
    admin_client: TestClient, mock_db: AsyncMock
) -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result)
    resp = admin_client.delete("/api/v1/admin/users/nonexistent")
    assert resp.status_code == 404


def test_update_nonexistent_user_returns_404(
    admin_client: TestClient, mock_db: AsyncMock
) -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result)
    resp = admin_client.patch("/api/v1/admin/users/nonexistent", json={"role": "leader"})
    assert resp.status_code == 404
```

- [ ] **Step 2: テスト実行**

```bash
pytest tests/unit/test_admin_router.py -v
```

Expected: 5 passed

- [ ] **Step 3: コミット**

```bash
git add tests/unit/test_admin_router.py
git commit -m "test: admin router — CRUD・権限チェック 5 件"
```

---

## Task 7: tasks_crud.py — visibility フィルタ + my_tasks_only + /similar

**Files:**
- Modify: `src/api/routers/tasks_crud.py`

- [ ] **Step 1: import を更新**

ファイル先頭の import を以下に更新：

```python
import re
import uuid
from collections import deque
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import array as pg_array
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.auth import ROLE_HIERARCHY, CurrentUser
from src.db.engine import get_db
from src.db.models import Task, TaskAssignee, TaskDependency, TaskTag, UserProfile
from src.models.task_web import (
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

- [ ] **Step 2: `list_tasks` に `my_tasks_only` パラメータ追加とフィルタ適用**

`list_tasks` の関数シグネチャに `my_tasks_only` を追加：

```python
@router.get("", response_model=TaskListResponse)
async def list_tasks(
    db: DbDep,
    current_user: CurrentUser,
    status_filter: TaskStatus | None = Query(default=None, alias="status"),  # noqa: B008
    assignee: str | None = None,
    project_id: uuid.UUID | None = None,
    section_id: uuid.UUID | None = None,
    tag: str | None = None,
    q: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    due_date_gte: date | None = Query(default=None),
    due_date_lte: date | None = Query(default=None),
    assignee_ids: list[str] | None = Query(default=None),
    my_tasks_only: bool = Query(default=False),
) -> TaskListResponse:
```

`if assignee_ids:` ブロックの直後（count_result の前）に追加：

```python
    # F-07 個人 ToDo フィルタ（ロールフィルタより先に適用）
    if my_tasks_only:
        query = query.where(
            Task.assignee_id == current_user.sub,
            Task.visibility == "private",
        )

    # ロールベース閲覧制御
    user_role = max(
        (ROLE_HIERARCHY.get(r, 0) for r in current_user.roles),
        default=0,
    )
    if user_role < ROLE_HIERARCHY["manager"]:
        if user_role >= ROLE_HIERARCHY["leader"]:
            if current_user.department_tags:
                dept_result = await db.execute(
                    select(UserProfile.user_id).where(
                        UserProfile.department_tags.op("?|")(
                            pg_array(current_user.department_tags)
                        )
                    )
                )
                dept_user_ids = list(dept_result.scalars().all())
                query = query.where(
                    or_(
                        Task.assignee_id.in_(dept_user_ids),
                        Task.visibility == "public",
                    )
                )
            else:
                query = query.where(Task.visibility == "public")
        else:
            query = query.where(
                or_(
                    Task.assignee_id == current_user.sub,
                    Task.visibility == "public",
                )
            )
    # manager / admin はフィルタなし
```

- [ ] **Step 3: `/similar` エンドポイントを `/{task_id}` の前に追加**

`@router.post("", ...)` の直後、`@router.get("/{task_id}", ...)` の直前に挿入：

```python
@router.get("/similar", response_model=list[SimilarTaskResponse])
async def similar_tasks(
    db: DbDep,
    current_user: CurrentUser,
    q: str = Query(min_length=3),
) -> list[SimilarTaskResponse]:
    tokens = [t for t in re.split(r"[　 、。，．・\s]+", q) if t]
    if not tokens:
        return []

    conditions = [Task.title.ilike(f"%{t}%") for t in tokens]
    result = await db.execute(select(Task).where(or_(*conditions)).limit(100))
    tasks_found = result.scalars().all()

    scored: list[tuple[float, Task]] = []
    for task in tasks_found:
        match_count = sum(1 for t in tokens if t.lower() in task.title.lower())
        score = match_count / len(tokens)
        if score >= 0.5:
            scored.append((score, task))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        SimilarTaskResponse(id=task.id, title=task.title, status=task.status, score=sc)
        for sc, task in scored[:5]
    ]
```

- [ ] **Step 4: pytest で既存テストが通ることを確認**

```bash
pytest tests/unit/test_tasks_crud_router.py tests/unit/test_reschedule.py -v
```

Expected: all passed

- [ ] **Step 5: コミット**

```bash
git add src/api/routers/tasks_crud.py
git commit -m "feat: list_tasks — ロール別閲覧制御・my_tasks_only・/similar エンドポイント"
```

---

## Task 8: test_visibility.py + test_similar_tasks.py

**Files:**
- Create: `tests/unit/test_visibility.py`
- Create: `tests/unit/test_similar_tasks.py`

- [ ] **Step 1: test_visibility.py を作成**

```python
# tests/unit/test_visibility.py
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.api.routers.tasks_crud import router
from src.db.engine import get_db


def _make_app(user: TokenPayload, mock_db: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app, raise_server_exceptions=False)


def _db_with_results(side_effects: list) -> AsyncMock:
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=side_effects)
    return db


def _empty_count() -> MagicMock:
    m = MagicMock()
    m.scalar_one.return_value = 0
    return m


def _empty_list() -> MagicMock:
    m = MagicMock()
    m.scalars.return_value.all.return_value = []
    return m


def test_member_list_tasks_returns_200() -> None:
    member = TokenPayload(sub="m1", roles=["member"], department_tags=[])
    db = _db_with_results([_empty_count(), _empty_list()])
    client = _make_app(member, db)
    resp = client.get("/api/v1/tasks")
    assert resp.status_code == 200


def test_manager_list_tasks_returns_200() -> None:
    manager = TokenPayload(sub="mg1", roles=["manager"], department_tags=[])
    db = _db_with_results([_empty_count(), _empty_list()])
    client = _make_app(manager, db)
    resp = client.get("/api/v1/tasks")
    assert resp.status_code == 200


def test_leader_with_dept_tags_list_tasks_returns_200() -> None:
    # leader はまず department_tags 一致ユーザー ID を DB 検索（3 回 execute）
    leader = TokenPayload(sub="l1", roles=["leader"], department_tags=["営業部"])
    dept_result = MagicMock()
    dept_result.scalars.return_value.all.return_value = ["user-x"]
    db = _db_with_results([dept_result, _empty_count(), _empty_list()])
    client = _make_app(leader, db)
    resp = client.get("/api/v1/tasks")
    assert resp.status_code == 200


def test_leader_without_dept_tags_list_tasks_returns_200() -> None:
    # department_tags が空の leader は public のみ（2 回 execute）
    leader = TokenPayload(sub="l2", roles=["leader"], department_tags=[])
    db = _db_with_results([_empty_count(), _empty_list()])
    client = _make_app(leader, db)
    resp = client.get("/api/v1/tasks")
    assert resp.status_code == 200
```

- [ ] **Step 2: test_similar_tasks.py を作成**

```python
# tests/unit/test_similar_tasks.py
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import TokenPayload, get_current_user
from src.api.routers.tasks_crud import router
from src.db.engine import get_db

_user = TokenPayload(sub="u1", roles=["member"], department_tags=[])


@pytest.fixture()
def mock_db() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def client(mock_db: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _user
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app, raise_server_exceptions=False)


def test_similar_route_exists(client: TestClient, mock_db: AsyncMock) -> None:
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=result)
    resp = client.get("/api/v1/tasks/similar?q=テスト")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_similar_requires_min_3_chars(client: TestClient) -> None:
    resp = client.get("/api/v1/tasks/similar?q=ab")
    assert resp.status_code == 422


def test_similar_returns_scored_results(client: TestClient, mock_db: AsyncMock) -> None:
    task = MagicMock()
    task.id = uuid.uuid4()
    task.title = "テストタスク作成"
    task.status = "not_started"
    result = MagicMock()
    result.scalars.return_value.all.return_value = [task]
    mock_db.execute = AsyncMock(return_value=result)
    resp = client.get("/api/v1/tasks/similar?q=テストタスク")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["score"] >= 0.5


def test_similar_excludes_low_score_results(client: TestClient, mock_db: AsyncMock) -> None:
    task = MagicMock()
    task.id = uuid.uuid4()
    task.title = "全く関係ない題名"
    task.status = "not_started"
    result = MagicMock()
    result.scalars.return_value.all.return_value = [task]
    mock_db.execute = AsyncMock(return_value=result)
    resp = client.get("/api/v1/tasks/similar?q=テストタスク作成")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 0
```

- [ ] **Step 3: 全テスト実行**

```bash
pytest tests/unit/ -v
```

Expected: 136 passed（既存 118 + 新規 5 admin + 4 visibility + 4 similar + 既存再確認）  
実際の件数は既存テスト数に依存。重要なのは **0 failed**。

- [ ] **Step 4: コミット**

```bash
git add tests/unit/test_visibility.py tests/unit/test_similar_tasks.py
git commit -m "test: visibility フィルタ・similar タスク検索 テスト追加"
```

---

## Task 9: frontend/src/lib/api.ts — 型追加

**Files:**
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: UserProfile に department_tags を追加**

既存の `UserProfile` インターフェースを修正：

```typescript
export interface UserProfile {
  user_id: string
  display_name: string
  email: string | null
  role: string
  capacity_hours_per_day: number
  department_tags: string[]
}
```

- [ ] **Step 2: AdminUser・SimilarTask 型を追加**

ファイル末尾（`RescheduleResponse` の後）に追記：

```typescript
export interface AdminUser {
  user_id: string
  display_name: string
  email: string | null
  role: string
  department_tags: string[]
  capacity_hours_per_day: number
}

export interface AdminUserCreate {
  user_id: string
  display_name: string
  email?: string | null
  role: string
  department_tags: string[]
  capacity_hours_per_day: number
}

export interface AdminUserUpdate {
  display_name?: string | null
  email?: string | null
  role?: string | null
  department_tags?: string[] | null
  capacity_hours_per_day?: number | null
}

export interface SimilarTask {
  id: string
  title: string
  status: string
  score: number
}
```

- [ ] **Step 3: TypeScript チェック**

```bash
cd frontend && npx tsc -b --noEmit
```

Expected: 0 errors

- [ ] **Step 4: コミット**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat: api.ts — AdminUser・SimilarTask 型・UserProfile に department_tags"
```

---

## Task 10: useAdminUsers.ts + useSimilarTasks.ts

**Files:**
- Create: `frontend/src/hooks/useAdminUsers.ts`
- Create: `frontend/src/hooks/useSimilarTasks.ts`

- [ ] **Step 1: useAdminUsers.ts を作成**

```typescript
// frontend/src/hooks/useAdminUsers.ts
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'
import type { AdminUser, AdminUserCreate, AdminUserUpdate } from '../lib/api'

export function useAdminUsers() {
  return useQuery<AdminUser[]>({
    queryKey: ['admin-users'],
    queryFn: async () => {
      const { data } = await api.get<AdminUser[]>('/admin/users')
      return data
    },
  })
}

export function useCreateAdminUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: AdminUserCreate) => {
      const { data } = await api.post<AdminUser>('/admin/users', body)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-users'] }),
  })
}

export function useUpdateAdminUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ userId, body }: { userId: string; body: AdminUserUpdate }) => {
      const { data } = await api.patch<AdminUser>(`/admin/users/${userId}`, body)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-users'] }),
  })
}

export function useDeleteAdminUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (userId: string) => {
      await api.delete(`/admin/users/${userId}`)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-users'] }),
  })
}
```

- [ ] **Step 2: useSimilarTasks.ts を作成**

```typescript
// frontend/src/hooks/useSimilarTasks.ts
import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'
import type { SimilarTask } from '../lib/api'

export function useSimilarTasks(title: string) {
  const [debounced, setDebounced] = useState(title)

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(title), 500)
    return () => clearTimeout(timer)
  }, [title])

  return useQuery<SimilarTask[]>({
    queryKey: ['similar-tasks', debounced],
    queryFn: async () => {
      const { data } = await api.get<SimilarTask[]>('/tasks/similar', {
        params: { q: debounced },
      })
      return data
    },
    enabled: debounced.length >= 3,
  })
}
```

- [ ] **Step 3: TypeScript チェック**

```bash
npx tsc -b --noEmit
```

Expected: 0 errors

- [ ] **Step 4: コミット**

```bash
git add frontend/src/hooks/useAdminUsers.ts frontend/src/hooks/useSimilarTasks.ts
git commit -m "feat: useAdminUsers・useSimilarTasks フック追加"
```

---

## Task 11: Admin Users ページ + App.tsx 更新

**Files:**
- Create: `frontend/src/pages/Admin/Users.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Admin/Users.tsx を作成**

```typescript
// frontend/src/pages/Admin/Users.tsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Button,
  Form,
  Input,
  InputNumber,
  message,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Typography,
} from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import {
  useAdminUsers,
  useCreateAdminUser,
  useDeleteAdminUser,
  useUpdateAdminUser,
} from '../../hooks/useAdminUsers'
import { useAuthStore } from '../../store/useAuthStore'
import type { AdminUser } from '../../lib/api'

const ROLE_OPTIONS = [
  { label: 'メンバー', value: 'member' },
  { label: 'リーダー', value: 'leader' },
  { label: 'マネージャー', value: 'manager' },
  { label: '管理者', value: 'admin' },
]

export default function AdminUsers() {
  const navigate = useNavigate()
  const roles = useAuthStore((s) => s.roles)

  // admin 以外はリダイレクト
  if (!roles.includes('admin')) {
    navigate('/')
    return null
  }

  const { data: users = [], isLoading } = useAdminUsers()
  const createUser = useCreateAdminUser()
  const updateUser = useUpdateAdminUser()
  const deleteUser = useDeleteAdminUser()

  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<AdminUser | null>(null)
  const [form] = Form.useForm()

  const existingTags = [...new Set(users.flatMap((u) => u.department_tags))]

  const handleOpen = (user?: AdminUser) => {
    setEditing(user ?? null)
    if (user) {
      form.setFieldsValue({
        display_name: user.display_name,
        email: user.email,
        role: user.role,
        department_tags: user.department_tags,
        capacity_hours_per_day: user.capacity_hours_per_day,
      })
    } else {
      form.resetFields()
      form.setFieldsValue({ role: 'member', department_tags: [], capacity_hours_per_day: 8.0 })
    }
    setOpen(true)
  }

  const handleOk = async () => {
    const values = await form.validateFields()
    try {
      if (editing) {
        await updateUser.mutateAsync({ userId: editing.user_id, body: values })
      } else {
        await createUser.mutateAsync(values as AdminUser & { user_id: string })
      }
      setOpen(false)
      form.resetFields()
    } catch {
      void message.error('操作に失敗しました')
    }
  }

  const columns = [
    { title: '氏名', dataIndex: 'display_name', key: 'display_name' },
    {
      title: 'メール',
      dataIndex: 'email',
      key: 'email',
      render: (v: string | null) => v ?? '—',
    },
    { title: 'ロール', dataIndex: 'role', key: 'role' },
    {
      title: '部門タグ',
      dataIndex: 'department_tags',
      key: 'department_tags',
      render: (tags: string[]) => tags.join(', ') || '—',
    },
    { title: '稼働時間/日', dataIndex: 'capacity_hours_per_day', key: 'cap' },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: AdminUser) => (
        <Space>
          <Button size="small" onClick={() => handleOpen(record)}>
            編集
          </Button>
          <Popconfirm
            title="このユーザーを削除しますか？"
            onConfirm={() => void deleteUser.mutateAsync(record.user_id)}
          >
            <Button size="small" danger>
              削除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Space style={{ width: '100%', justifyContent: 'space-between' }}>
        <Typography.Title level={3} style={{ margin: 0 }}>
          ユーザー管理
        </Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => handleOpen()}>
          ユーザー追加
        </Button>
      </Space>

      <Table rowKey="user_id" loading={isLoading} dataSource={users} columns={columns} />

      <Modal
        title={editing ? 'ユーザー編集' : 'ユーザー追加'}
        open={open}
        onOk={() => void handleOk()}
        onCancel={() => {
          setOpen(false)
          form.resetFields()
        }}
        confirmLoading={createUser.isPending || updateUser.isPending}
      >
        <Form form={form} layout="vertical">
          {!editing && (
            <>
              <Form.Item name="user_id" label="ユーザーID" rules={[{ required: true }]}>
                <Input />
              </Form.Item>
              <Form.Item name="display_name" label="氏名" rules={[{ required: true }]}>
                <Input />
              </Form.Item>
              <Form.Item name="email" label="メールアドレス">
                <Input />
              </Form.Item>
            </>
          )}
          {editing && (
            <Form.Item name="display_name" label="氏名" rules={[{ required: true }]}>
              <Input />
            </Form.Item>
          )}
          <Form.Item name="role" label="ロール">
            <Select options={ROLE_OPTIONS} />
          </Form.Item>
          <Form.Item name="department_tags" label="部門タグ">
            <Select
              mode="tags"
              options={existingTags.map((t) => ({ label: t, value: t }))}
            />
          </Form.Item>
          <Form.Item name="capacity_hours_per_day" label="稼働時間/日">
            <InputNumber min={0} max={24} step={0.5} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  )
}
```

- [ ] **Step 2: useAuthStore の roles 確認**

`frontend/src/store/useAuthStore.ts` に `roles: string[]` があることを確認。なければ追加する。

- [ ] **Step 3: App.tsx に /admin/users を追加**

`App.tsx` の import に追加：
```typescript
import AdminUsers from './pages/Admin/Users'
import { SettingOutlined } from '@ant-design/icons'
```

`NAV_ITEMS` に条件付き項目を追加（admin のみ表示するため、コンポーネント内で条件分岐）：

`AppLayout` 関数内に追加。まず `useAuthStore` で roles を取得：
```typescript
function AppLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const roles = useAuthStore((s) => s.roles)
  // ...

  const NAV_ITEMS_WITH_ADMIN = [
    ...NAV_ITEMS,
    ...(roles.includes('admin')
      ? [{ key: '/admin/users', icon: <SettingOutlined />, label: 'ユーザー管理' }]
      : []),
  ]
```

`<Menu items={NAV_ITEMS}>` を `<Menu items={NAV_ITEMS_WITH_ADMIN}>` に変更。

`<Routes>` に追加：
```typescript
<Route path="/admin/users" element={<AdminUsers />} />
```

- [ ] **Step 4: TypeScript チェック**

```bash
npx tsc -b --noEmit
```

Expected: 0 errors

- [ ] **Step 5: コミット**

```bash
git add frontend/src/pages/Admin/Users.tsx frontend/src/App.tsx
git commit -m "feat: Admin Users ページ・サイドバー admin 限定表示"
```

---

## Task 12: Tasks/index.tsx — F-07 ToDo スイッチ + F-04 類似タスク警告

**Files:**
- Modify: `frontend/src/pages/Tasks/index.tsx`

- [ ] **Step 1: import 追加**

```typescript
import { useState, useEffect } from 'react'
import {
  Alert,
  Button,
  Form,
  Input,
  message,
  Modal,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
} from 'antd'
import { useSimilarTasks } from '../../hooks/useSimilarTasks'
```

- [ ] **Step 2: state 追加と handleCreate 更新**

既存の `useState` 群に追加：
```typescript
const [myTasksOnly, setMyTasksOnly] = useState(false)
const [newTitle, setNewTitle] = useState('')
```

`useTasks` の呼び出しに `my_tasks_only` を追加：
```typescript
const { data: taskList, isLoading } = useTasks({
  status: statusFilter || undefined,
  project_id: projectFilter,
  section_id: sectionFilter,
  q: searchQ || undefined,
  my_tasks_only: myTasksOnly || undefined,
})
```

`useSimilarTasks` フック追加：
```typescript
const { data: similarTasks = [] } = useSimilarTasks(newTitle)
```

- [ ] **Step 3: フィルタバーに ToDo スイッチを追加**

`<Space wrap>` 内の最後に追加：
```tsx
<Space>
  <Switch checked={myTasksOnly} onChange={setMyTasksOnly} />
  <span>自分の ToDo のみ</span>
</Space>
```

- [ ] **Step 4: 作成モーダルに visibility Select と類似タスク警告を追加**

`handleCreate` の `await form.validateFields()` 後に `form.resetFields()` で `setNewTitle('')` を追加：
```typescript
const handleCreate = async () => {
  const values = await form.validateFields()
  try {
    await createTask.mutateAsync(values as { title: string; description?: string; visibility?: string })
    form.resetFields()
    setNewTitle('')
    setOpen(false)
  } catch {
    void message.error('タスクの作成に失敗しました')
  }
}
```

モーダル内の `<Form>` に追加：
```tsx
<Form form={form} layout="vertical">
  <Form.Item name="title" label="タスク名" rules={[{ required: true }]}>
    <Input value={newTitle} onChange={(e) => setNewTitle(e.target.value)} />
  </Form.Item>
  {similarTasks.length > 0 && (
    <Alert
      type="warning"
      style={{ marginBottom: 12 }}
      message={`類似タスクが見つかりました（${similarTasks.length}件）`}
      description={
        <ul style={{ margin: 0, paddingLeft: 16 }}>
          {similarTasks.map((t) => (
            <li key={t.id}>
              {t.title} ({t.status})
            </li>
          ))}
        </ul>
      }
    />
  )}
  <Form.Item name="description" label="説明">
    <Input.TextArea rows={3} />
  </Form.Item>
  <Form.Item name="visibility" label="公開範囲" initialValue="team">
    <Select
      options={[
        { label: 'チーム共有', value: 'team' },
        { label: '全公開', value: 'public' },
        { label: '個人（ToDo）', value: 'private' },
      ]}
    />
  </Form.Item>
</Form>
```

- [ ] **Step 5: useTasks の型定義に my_tasks_only を追加**

`frontend/src/hooks/useTasks.ts` の `TaskFilters` インターフェースに：
```typescript
interface TaskFilters {
  status?: string
  assignee?: string
  project_id?: string
  section_id?: string
  q?: string
  tag?: string
  limit?: number
  offset?: number
  my_tasks_only?: boolean
}
```

- [ ] **Step 6: TypeScript チェック**

```bash
npx tsc -b --noEmit
```

Expected: 0 errors

- [ ] **Step 7: コミット**

```bash
git add frontend/src/pages/Tasks/index.tsx frontend/src/hooks/useTasks.ts
git commit -m "feat: Tasks — F-07 自分の ToDo スイッチ・F-04 類似タスク警告・visibility 選択"
```

---

## Task 13: Schedule/index.tsx — F-11 週次 D&D グリッド

**Files:**
- Modify: `frontend/src/pages/Schedule/index.tsx`

- [ ] **Step 1: Schedule/index.tsx 全体を書き換え**

```typescript
// frontend/src/pages/Schedule/index.tsx
import { useMemo } from 'react'
import { Card, Space, Tag, Typography } from 'antd'
import {
  DndContext,
  type DragEndEvent,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import { CSS } from '@dnd-kit/utilities'
import dayjs from 'dayjs'
import 'dayjs/locale/ja'
import { useTasksForView } from '../../hooks/useTasksForView'
import { useUpdateTask } from '../../hooks/useTasks'
import type { Task } from '../../lib/api'

dayjs.locale('ja')

function getWeekDays(): dayjs.Dayjs[] {
  const today = dayjs()
  return Array.from({ length: 7 }, (_, i) => today.subtract(3, 'day').add(i, 'day'))
}

function TaskCard({ task }: { task: Task }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: task.id,
    data: { task },
  })
  return (
    <div
      ref={setNodeRef}
      style={{
        transform: CSS.Transform.toString(transform),
        opacity: isDragging ? 0.5 : 1,
        cursor: 'grab',
        marginBottom: 4,
      }}
      {...listeners}
      {...attributes}
    >
      <Card size="small" style={{ fontSize: 12 }}>
        <div style={{ fontWeight: 500 }}>{task.title}</div>
        {task.due_date && (
          <Tag color="blue" style={{ marginTop: 4, fontSize: 10 }}>
            期限: {task.due_date}
          </Tag>
        )}
      </Card>
    </div>
  )
}

function DateColumn({ day, tasks }: { day: dayjs.Dayjs; tasks: Task[] }) {
  const isToday = day.isSame(dayjs(), 'day')
  const dateKey = day.format('YYYY-MM-DD')
  const { setNodeRef, isOver } = useDroppable({ id: dateKey })

  return (
    <div
      ref={setNodeRef}
      style={{
        flex: 1,
        minWidth: 120,
        minHeight: 200,
        padding: 8,
        border: `2px solid ${isOver ? '#1677ff' : isToday ? '#91caff' : '#d9d9d9'}`,
        borderRadius: 6,
        background: isOver ? '#e6f4ff' : isToday ? '#f0f7ff' : 'white',
        transition: 'border-color 0.15s, background 0.15s',
      }}
    >
      <div
        style={{
          fontWeight: isToday ? 700 : 400,
          marginBottom: 8,
          textAlign: 'center',
          fontSize: 12,
          color: isToday ? '#1677ff' : '#333',
        }}
      >
        {day.format('M/D')}
        <br />
        {day.format('ddd')}
      </div>
      {tasks.map((t) => (
        <TaskCard key={t.id} task={t} />
      ))}
    </div>
  )
}

function UnassignedColumn({ tasks }: { tasks: Task[] }) {
  const { setNodeRef, isOver } = useDroppable({ id: '__unassigned__' })
  return (
    <div
      ref={setNodeRef}
      style={{
        width: 140,
        minHeight: 200,
        padding: 8,
        border: `2px dashed ${isOver ? '#1677ff' : '#d9d9d9'}`,
        borderRadius: 6,
        background: isOver ? '#e6f4ff' : '#fafafa',
        flexShrink: 0,
      }}
    >
      <div
        style={{
          fontWeight: 400,
          marginBottom: 8,
          textAlign: 'center',
          fontSize: 12,
          color: '#888',
        }}
      >
        未配置
      </div>
      {tasks.map((t) => (
        <TaskCard key={t.id} task={t} />
      ))}
    </div>
  )
}

export default function Schedule() {
  const days = useMemo(() => getWeekDays(), [])

  const { data: tasks = [] } = useTasksForView({ limit: 200 })
  const updateTask = useUpdateTask()

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
  )

  const tasksByDate = useMemo(() => {
    const map: Record<string, Task[]> = { __unassigned__: [] }
    for (const day of days) map[day.format('YYYY-MM-DD')] = []
    for (const task of tasks) {
      const key = task.start_date ?? '__unassigned__'
      if (key in map) map[key].push(task)
      else map['__unassigned__'].push(task)
    }
    return map
  }, [tasks, days])

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event
    if (!over) return
    const taskId = active.id as string
    const newDate = over.id === '__unassigned__' ? null : (over.id as string)
    updateTask.mutate({ id: taskId, start_date: newDate })
  }

  return (
    <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
      <Space direction="vertical" style={{ width: '100%' }} size={16}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          スケジュール — 週次ビュー
        </Typography.Title>
        <div style={{ display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 8 }}>
          <UnassignedColumn tasks={tasksByDate['__unassigned__'] ?? []} />
          {days.map((day) => (
            <DateColumn
              key={day.format('YYYY-MM-DD')}
              day={day}
              tasks={tasksByDate[day.format('YYYY-MM-DD')] ?? []}
            />
          ))}
        </div>
      </Space>
    </DndContext>
  )
}
```

- [ ] **Step 2: TypeScript チェック**

```bash
npx tsc -b --noEmit
```

Expected: 0 errors

- [ ] **Step 3: 全バックエンドテスト確認**

```bash
cd .. && pytest tests/unit/ -v
```

Expected: 0 failed

- [ ] **Step 4: コミット**

```bash
git add frontend/src/pages/Schedule/index.tsx
git commit -m "feat: Schedule — F-11 週次 D&D グリッド（start_date 更新）"
```

---

## Task 14: 最終確認 + docs 更新

**Files:**
- Modify: `docs/progress.md`
- Modify: `docs/tasks.md`

- [ ] **Step 1: バックエンドテスト全件実行**

```bash
pytest tests/unit/ -v --tb=short
```

Expected: 0 failed（合計件数は Task 8 Step 3 で確認済み）

- [ ] **Step 2: TypeScript チェック**

```bash
cd frontend && npx tsc -b --noEmit
```

Expected: 0 errors

- [ ] **Step 3: docs/progress.md を更新**

`現在のフェーズ` 行を更新：
```
**Phase: Web App Phase 2B-2（ユーザー管理・権限制御・UX 強化）✅ 完了 → Phase 2B-3 以降へ**
```

完了した作業として以下を追記：
```
- **[Web App Phase 2B-2 — 全 14 タスク完了]** ユーザー管理・権限制御・UX 強化
  - Alembic 0003（start_date 補完）・0004（department_tags JSONB）
  - ハイブリッド認証: JWT-first / DB-fallback・ROLE_HIERARCHY 公開
  - Admin API: GET/POST/PATCH/DELETE /api/v1/admin/users（admin 権限ガード）
  - ロールベース閲覧制御: member=own+public, leader=dept+public, manager/admin=全件
  - F-07: my_tasks_only フィルタ・タスク作成時 visibility=private 選択
  - F-04: /tasks/similar（トークン分割 ILIKE・スコア 0.5 以上・最大 5 件）
  - F-11: Schedule ページ週次 D&D グリッド（start_date 更新）
  - Admin Users ページ（/admin/users）・部門タグ Select mode=tags
```

- [ ] **Step 4: docs/tasks.md の Phase 2B チェックボックスを更新**

以下を `[x]` に変更：
```
- [x] **F-11 D&D**: タスクをスケジュール画面でドラッグ＆ドロップ配置
- [x] **F-07 個人 ToDo**: visibility=private タスクの個人専用ビュー・フィルタ
- [x] **F-04 二重登録防止**: タスク作成時の類似タスク検索・警告表示 UI
```

- [ ] **Step 5: コミット・push**

```bash
git add docs/progress.md docs/tasks.md
git commit -m "docs: Phase 2B-2 完了記録・進捗更新"
git push origin master
```

---

## Self-Review チェックリスト

実装完了後に以下を確認：

| 確認項目 | 対応タスク |
|---------|-----------|
| Alembic 0003/0004 が `alembic upgrade head` で適用できる | Task 1, 2 |
| `department_tags` が JSONB 型（`?|` 演算子が動く） | Task 2 |
| `GET /similar` が `/{task_id}` より前に定義されている | Task 7 |
| admin 以外が `/api/v1/admin/users` を叩くと 403 | Task 6 |
| member ロールが他人の private タスクを `GET /tasks` で取得できない | Task 7 |
| `my_tasks_only=true` が `visibility=private` かつ `assignee_id=self` を返す | Task 7 |
| Schedule ページにタスクをドロップすると `start_date` が更新される | Task 13 |
| TypeScript strict 0 errors | Task 14 |
| pytest 0 failed | Task 14 |
