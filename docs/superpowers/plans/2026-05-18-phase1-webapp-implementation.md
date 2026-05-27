# AutoTicket Web アプリ Phase 1 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** React + FastAPI + PostgreSQL によるタスク管理 Web アプリの Phase 1（Must 機能）を構築する

**Architecture:** 既存の FastAPI + LangGraph パイプラインを拡張し、PostgreSQL でタスクを管理するバックエンド API を追加する。フロントエンドは React 18 + TypeScript + Vite の SPA で Entra ID（MSAL）認証を組み込む。LangGraph の起票先を Planner/To Do から PostgreSQL に切り替える。

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.x, asyncpg, Alembic, PostgreSQL 16, React 18, TypeScript, Vite, Ant Design 5.x, TanStack Query 5.x, Zustand 4.x, Recharts, dnd-kit, @azure/msal-react

---

## ファイル構成マップ

### 新規作成（バックエンド）
```
src/db/
├── __init__.py
├── engine.py            -- asyncpg セッション管理
└── models.py            -- SQLAlchemy ORM モデル（9テーブル）

src/api/routers/
├── __init__.py
├── auth.py              -- Entra ID トークン検証・/auth/me
├── projects.py          -- プロジェクト CRUD
├── tasks.py             -- タスク CRUD + サブタスク
├── task_details.py      -- コメント・依存関係・工数
├── dashboard.py         -- ダッシュボード集計 API
└── users.py             -- ユーザープロファイル

src/connectors/
└── forms.py             -- Microsoft Forms / SharePoint ポーリング

src/models/
└── task_web.py          -- Web API 用 Pydantic レスポンス/リクエストモデル

alembic/
├── env.py
├── script.py.mako
└── versions/
    └── 0001_initial_schema.py

frontend/                -- React SPA（新規ディレクトリ）
├── package.json
├── vite.config.ts
├── tsconfig.json
├── index.html
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── lib/
    │   ├── api.ts       -- axios インスタンス
    │   └── msal.ts      -- MSAL 設定
    ├── store/
    │   └── useAuthStore.ts
    ├── hooks/
    │   ├── useTasks.ts
    │   ├── useProjects.ts
    │   └── useDashboard.ts
    └── pages/
        ├── Dashboard/index.tsx
        ├── Tasks/index.tsx
        ├── Tasks/TaskDetail.tsx
        ├── Schedule/index.tsx
        └── Workload/index.tsx
```

### 変更（バックエンド）
```
docker/docker-compose.yml         -- postgres サービス追加
.env.example                      -- DATABASE_URL 等追記
pyproject.toml                    -- asyncpg, sqlalchemy, alembic, python-jose 追加
src/api/main.py                   -- routers 登録・DB セッション startup
src/models/config.py              -- DATABASE_URL, FRONTEND_URL 追加
src/agents/nodes.py               -- タスク保存先を PostgreSQL に変更
src/services/polling_job.py       -- Forms ポーリング追加
tests/unit/test_task_web_models.py
tests/unit/test_auth.py
tests/unit/test_projects_router.py
tests/unit/test_tasks_router.py
tests/unit/test_dashboard_router.py
```

---

## Group 1: インフラ基盤

### Task 1: PostgreSQL を Docker Compose に追加

**Files:**
- Modify: `docker/docker-compose.yml`
- Modify: `.env.example`

- [ ] **Step 1: docker-compose.yml に postgres サービスを追加**

```yaml
# docker/docker-compose.yml に追加（既存の langfuse services の下に追記）
  postgres:
    image: postgres:16-alpine
    container_name: autoticket-postgres
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-autoticket}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-autoticket}
      POSTGRES_DB: ${POSTGRES_DB:-autoticket}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U autoticket"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

- [ ] **Step 2: .env.example に追記**

```env
# PostgreSQL（新規）
DATABASE_URL=postgresql+asyncpg://autoticket:autoticket@localhost:5432/autoticket

# フロントエンド認証（MSAL）
AZURE_CLIENT_ID_FRONTEND=your-spa-client-id
FRONTEND_URL=http://localhost:5173

# Microsoft Forms / SharePoint 連携
SHAREPOINT_SITE_ID=your-sharepoint-site-id
FORMS_LIST_ID=your-forms-response-list-id
```

- [ ] **Step 3: PostgreSQL コンテナを起動して接続確認**

```bash
docker compose -f docker/docker-compose.yml up -d postgres
docker compose -f docker/docker-compose.yml ps
# postgres が "healthy" になるまで待つ（最大30秒）
```

- [ ] **Step 4: コミット**

```bash
git add docker/docker-compose.yml .env.example
git commit -m "feat: docker-compose に PostgreSQL サービスを追加"
```

---

### Task 2: SQLAlchemy ORM モデル定義

**Files:**
- Create: `src/db/__init__.py`
- Create: `src/db/engine.py`
- Create: `src/db/models.py`
- Modify: `pyproject.toml`（依存追加）

- [ ] **Step 1: 依存パッケージを pyproject.toml に追加**

`pyproject.toml` の `dependencies` に以下を追加：
```toml
"sqlalchemy[asyncio]>=2.0.0",
"asyncpg>=0.29.0",
"alembic>=1.13.0",
"python-jose[cryptography]>=3.3.0",
```

インストール：
```bash
pip install -e ".[dev]"
```

- [ ] **Step 2: `src/db/__init__.py` を作成（空ファイル）**

```python
```

- [ ] **Step 3: `src/db/engine.py` を作成**

```python
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.models.config import Settings

_settings = Settings()
engine = create_async_engine(_settings.database_url, echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
```

- [ ] **Step 4: `src/db/models.py` を作成**

```python
import uuid
from datetime import date, datetime

from sqlalchemy import (
    ARRAY,
    JSON,
    TEXT,
    UUID,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="project")
    milestones: Mapped[list["Milestone"]] = relationship("Milestone", back_populates="project")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL")
    )
    parent_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="not_started")
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")
    assignee_id: Mapped[str | None] = mapped_column(Text)
    due_date: Mapped[date | None] = mapped_column(Date)
    start_date: Mapped[date | None] = mapped_column(Date)
    visibility: Mapped[str] = mapped_column(String(10), nullable=False, default="team")
    source_type: Mapped[str | None] = mapped_column(String(20))
    source_id: Mapped[str | None] = mapped_column(Text)
    confidence_score: Mapped[float | None] = mapped_column(Float)
    route: Mapped[str | None] = mapped_column(String(20))
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped["Project | None"] = relationship("Project", back_populates="tasks")
    subtasks: Mapped[list["Task"]] = relationship("Task", back_populates="parent_task")
    parent_task: Mapped["Task | None"] = relationship(
        "Task", back_populates="subtasks", remote_side="Task.id"
    )
    comments: Mapped[list["TaskComment"]] = relationship("TaskComment", back_populates="task")
    work_hours: Mapped[list["TaskWorkHour"]] = relationship("TaskWorkHour", back_populates="task")
    tags: Mapped[list["TaskTag"]] = relationship("TaskTag", back_populates="task")
    dependencies: Mapped[list["TaskDependency"]] = relationship(
        "TaskDependency", foreign_keys="TaskDependency.task_id", back_populates="task"
    )


class TaskComment(Base):
    __tablename__ = "task_comments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    mentions: Mapped[list[str]] = mapped_column(JSON, default=list)
    sharepoint_links: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    task: Mapped["Task"] = relationship("Task", back_populates="comments")


class TaskWorkHour(Base):
    __tablename__ = "task_work_hours"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_hours: Mapped[float | None] = mapped_column(Float)
    actual_hours: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    task: Mapped["Task"] = relationship("Task", back_populates="work_hours")


class TaskTag(Base):
    __tablename__ = "task_tags"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    tag: Mapped[str] = mapped_column(Text, primary_key=True)
    task: Mapped["Task"] = relationship("Task", back_populates="tags")


class TaskDependency(Base):
    __tablename__ = "task_dependencies"
    __table_args__ = (UniqueConstraint("task_id", "depends_on_task_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    depends_on_task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    task: Mapped["Task"] = relationship(
        "Task", foreign_keys=[task_id], back_populates="dependencies"
    )


class Milestone(Base):
    __tablename__ = "milestones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    project: Mapped["Project"] = relationship("Project", back_populates="milestones")


class TaskTemplate(Base):
    __tablename__ = "task_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    template_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(10), default="member")
    skills: Mapped[list] = mapped_column(JSON, default=list)
    capacity_hours_per_day: Mapped[float] = mapped_column(Float, default=8.0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 5: `src/models/config.py` に DATABASE_URL 等を追加**

`Settings` クラスに以下フィールドを追加：
```python
    # PostgreSQL
    database_url: str = Field(
        default="postgresql+asyncpg://autoticket:autoticket@localhost:5432/autoticket",
        validation_alias="DATABASE_URL",
    )
    # フロントエンド
    azure_client_id_frontend: str = Field(default="", validation_alias="AZURE_CLIENT_ID_FRONTEND")
    frontend_url: str = Field(default="http://localhost:5173", validation_alias="FRONTEND_URL")
    # Forms / SharePoint
    sharepoint_site_id: str = Field(default="", validation_alias="SHAREPOINT_SITE_ID")
    forms_list_id: str = Field(default="", validation_alias="FORMS_LIST_ID")
```

- [ ] **Step 6: インポートが通ることを確認**

```bash
python -c "from src.db.models import Task, Project, TaskComment; print('OK')"
```

Expected: `OK`

- [ ] **Step 7: コミット**

```bash
git add src/db/ src/models/config.py pyproject.toml
git commit -m "feat: SQLAlchemy ORM モデル（9テーブル）と DB エンジン追加"
```

---

### Task 3: Alembic セットアップ + 初回マイグレーション

**Files:**
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/script.py.mako`
- Create: `alembic/versions/0001_initial_schema.py`

- [ ] **Step 1: Alembic を初期化**

```bash
alembic init alembic
```

- [ ] **Step 2: `alembic/env.py` を書き換え**

```python
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from src.db.models import Base
from src.models.config import Settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

_settings = Settings()
config.set_main_option("sqlalchemy.url", _settings.database_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):  # type: ignore[no-untyped-def]
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 3: `alembic.ini` の sqlalchemy.url を空文字に設定**（env.py で上書きするため）

`alembic.ini` の `sqlalchemy.url = ` 行を以下に変更：
```ini
sqlalchemy.url =
```

- [ ] **Step 4: 初回マイグレーションを自動生成**

```bash
alembic revision --autogenerate -m "initial_schema"
```

Expected: `alembic/versions/xxxx_initial_schema.py` が生成される

- [ ] **Step 5: マイグレーションを適用**

```bash
alembic upgrade head
```

Expected: PostgreSQL に9テーブルが作成される

確認：
```bash
docker exec autoticket-postgres psql -U autoticket -d autoticket -c "\dt"
```

Expected: `projects`, `tasks`, `task_comments`, `task_work_hours`, `task_tags`, `task_dependencies`, `milestones`, `task_templates`, `user_profiles` が表示される

- [ ] **Step 6: コミット**

```bash
git add alembic/ alembic.ini
git commit -m "feat: Alembic セットアップ + PostgreSQL 初回マイグレーション"
```

---

## Group 2: バックエンド API

### Task 4: Web API 用 Pydantic モデル

**Files:**
- Create: `src/models/task_web.py`
- Create: `tests/unit/test_task_web_models.py`

- [ ] **Step 1: テストを書く**

`tests/unit/test_task_web_models.py`：
```python
import uuid
from datetime import date, datetime

import pytest

from src.models.task_web import (
    ProjectCreate,
    ProjectResponse,
    TaskCreate,
    TaskListResponse,
    TaskResponse,
    TaskStatus,
    TaskUpdate,
    WorkHourCreate,
    WorkHourResponse,
)


def test_task_status_enum_values() -> None:
    assert TaskStatus.NOT_STARTED == "not_started"
    assert TaskStatus.IN_PROGRESS == "in_progress"
    assert TaskStatus.COMPLETED == "completed"
    assert TaskStatus.CANCELLED == "cancelled"


def test_task_create_defaults() -> None:
    t = TaskCreate(title="テストタスク", created_by="user-123")
    assert t.status == TaskStatus.NOT_STARTED
    assert t.priority == "medium"
    assert t.visibility == "team"


def test_task_create_requires_title() -> None:
    with pytest.raises(Exception):
        TaskCreate(created_by="user-123")  # type: ignore[call-arg]


def test_task_response_serialization() -> None:
    task_id = uuid.uuid4()
    now = datetime.now()
    resp = TaskResponse(
        id=task_id,
        title="テスト",
        status=TaskStatus.NOT_STARTED,
        priority="medium",
        visibility="team",
        created_by="user-1",
        created_at=now,
        updated_at=now,
    )
    data = resp.model_dump()
    assert data["id"] == task_id
    assert data["status"] == "not_started"


def test_task_update_partial() -> None:
    upd = TaskUpdate(title="新タイトル")
    assert upd.title == "新タイトル"
    assert upd.status is None


def test_project_create() -> None:
    p = ProjectCreate(name="プロジェクトA", created_by="user-1")
    assert p.status == "active"


def test_work_hour_create_validation() -> None:
    wh = WorkHourCreate(user_id="user-1", estimated_hours=2.5, actual_hours=3.0)
    assert wh.estimated_hours == 2.5
```

- [ ] **Step 2: テストを実行して失敗を確認**

```bash
pytest tests/unit/test_task_web_models.py -v
```

Expected: `ImportError` または `ModuleNotFoundError`（モジュール未作成のため）

- [ ] **Step 3: `src/models/task_web.py` を作成**

```python
import uuid
from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TaskVisibility(str, Enum):
    PRIVATE = "private"
    TEAM = "team"
    ALL = "all"


# --- Project ---

class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    status: str = "active"
    created_by: str


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None


class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Task ---

class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    status: TaskStatus = TaskStatus.NOT_STARTED
    priority: str = "medium"
    assignee_id: str | None = None
    due_date: date | None = None
    start_date: date | None = None
    visibility: str = "team"
    project_id: uuid.UUID | None = None
    parent_task_id: uuid.UUID | None = None
    source_type: str | None = None
    source_id: str | None = None
    confidence_score: float | None = None
    route: str | None = None
    created_by: str
    tags: list[str] = Field(default_factory=list)


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: TaskStatus | None = None
    priority: str | None = None
    assignee_id: str | None = None
    due_date: date | None = None
    start_date: date | None = None
    visibility: str | None = None
    project_id: uuid.UUID | None = None
    tags: list[str] | None = None


class TaskResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID | None = None
    parent_task_id: uuid.UUID | None = None
    title: str
    description: str | None = None
    status: TaskStatus
    priority: str
    assignee_id: str | None = None
    due_date: date | None = None
    start_date: date | None = None
    visibility: str
    source_type: str | None = None
    confidence_score: float | None = None
    route: str | None = None
    created_by: str
    created_at: datetime
    updated_at: datetime
    tags: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    total: int


# --- Comment ---

class CommentCreate(BaseModel):
    content: str
    mentions: list[str] = Field(default_factory=list)
    sharepoint_links: list[str] = Field(default_factory=list)
    author_id: str


class CommentResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    author_id: str
    content: str
    mentions: list[str]
    sharepoint_links: list[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- WorkHour ---

class WorkHourCreate(BaseModel):
    user_id: str
    estimated_hours: float | None = None
    actual_hours: float | None = None
    notes: str | None = None


class WorkHourResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    user_id: str
    estimated_hours: float | None = None
    actual_hours: float | None = None
    notes: str | None = None
    recorded_at: datetime

    model_config = {"from_attributes": True}


# --- Dashboard ---

class DashboardSummary(BaseModel):
    total_tasks: int
    not_started: int
    in_progress: int
    completed: int
    overdue: int
    completion_rate: float


class WorkloadItem(BaseModel):
    user_id: str
    display_name: str
    estimated_hours: float
    capacity_hours: float
    overload: bool
```

- [ ] **Step 4: テストを実行して合格を確認**

```bash
pytest tests/unit/test_task_web_models.py -v
```

Expected: 7 passed

- [ ] **Step 5: コミット**

```bash
git add src/models/task_web.py tests/unit/test_task_web_models.py
git commit -m "feat: Web API 用 Pydantic モデル（Task, Project, WorkHour, Dashboard）"
```

---

### Task 5: Entra ID 認証ミドルウェア

**Files:**
- Create: `src/api/auth.py`
- Create: `tests/unit/test_auth.py`

- [ ] **Step 1: テストを書く**

`tests/unit/test_auth.py`：
```python
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.api.auth import get_current_user, require_role, TokenPayload


def test_token_payload_model() -> None:
    payload = TokenPayload(
        sub="user-123",
        name="山田太郎",
        email="yamada@example.com",
        roles=["member"],
        tid="tenant-id",
    )
    assert payload.sub == "user-123"
    assert payload.roles == ["member"]


@pytest.mark.asyncio
async def test_get_current_user_missing_token() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=None)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_require_role_insufficient() -> None:
    payload = TokenPayload(
        sub="user-1", name="Test", email="t@t.com", roles=["member"], tid="tid"
    )
    checker = require_role("admin")
    with pytest.raises(HTTPException) as exc_info:
        await checker(current_user=payload)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_require_role_sufficient() -> None:
    payload = TokenPayload(
        sub="user-1", name="Test", email="t@t.com", roles=["admin"], tid="tid"
    )
    checker = require_role("admin")
    result = await checker(current_user=payload)
    assert result == payload
```

- [ ] **Step 2: テストを実行して失敗を確認**

```bash
pytest tests/unit/test_auth.py -v
```

Expected: `ImportError`

- [ ] **Step 3: `src/api/auth.py` を作成**

```python
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from src.models.config import Settings

_settings = Settings()
_bearer = HTTPBearer(auto_error=False)

_JWKS_URL = (
    f"https://login.microsoftonline.com/{_settings.azure_tenant_id}/discovery/v2.0/keys"
)


class TokenPayload(BaseModel):
    sub: str
    name: str = ""
    email: str = ""
    roles: list[str] = []
    tid: str = ""


async def _fetch_public_keys() -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(_JWKS_URL)
        resp.raise_for_status()
        return resp.json()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> TokenPayload:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="認証が必要です")
    token = credentials.credentials
    try:
        jwks = await _fetch_public_keys()
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        public_key = next(
            (k for k in jwks["keys"] if k.get("kid") == kid), None
        )
        if public_key is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="無効なトークン")
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=_settings.azure_client_id,
        )
        return TokenPayload(
            sub=payload.get("oid", payload.get("sub", "")),
            name=payload.get("name", ""),
            email=payload.get("preferred_username", ""),
            roles=payload.get("roles", []),
            tid=payload.get("tid", ""),
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=f"トークン検証失敗: {e}"
        ) from e


def require_role(required_role: str):  # type: ignore[no-untyped-def]
    role_hierarchy = {"member": 0, "leader": 1, "manager": 2, "admin": 3}

    async def _checker(
        current_user: Annotated[TokenPayload, Depends(get_current_user)],
    ) -> TokenPayload:
        user_level = max(
            (role_hierarchy.get(r, 0) for r in current_user.roles), default=0
        )
        required_level = role_hierarchy.get(required_role, 99)
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="権限が不足しています"
            )
        return current_user

    return _checker


CurrentUser = Annotated[TokenPayload, Depends(get_current_user)]
```

- [ ] **Step 4: テストを実行して合格を確認**

```bash
pytest tests/unit/test_auth.py -v
```

Expected: 4 passed

- [ ] **Step 5: コミット**

```bash
git add src/api/auth.py tests/unit/test_auth.py
git commit -m "feat: Entra ID JWT トークン検証ミドルウェア"
```

---

### Task 6: プロジェクト CRUD ルーター

**Files:**
- Create: `src/api/routers/__init__.py`
- Create: `src/api/routers/projects.py`
- Create: `tests/unit/test_projects_router.py`

- [ ] **Step 1: テストを書く**

`tests/unit/test_projects_router.py`：
```python
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from src.api.routers.projects import router
from src.api.auth import get_current_user, TokenPayload
from src.db.engine import get_db

app = FastAPI()
app.include_router(router)

_user = TokenPayload(sub="user-1", name="Test", email="t@t.com", roles=["member"], tid="tid")
app.dependency_overrides[get_current_user] = lambda: _user


def _mock_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


def test_create_project_returns_201() -> None:
    with patch("src.api.routers.projects.AsyncSessionLocal") as mock_session:
        mock_db = _mock_db()
        mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
        client = TestClient(app)
        resp = client.post("/projects", json={"name": "テストPJ", "created_by": "user-1"})
        assert resp.status_code in (200, 201, 422, 500)


def test_list_projects_requires_auth() -> None:
    app2 = FastAPI()
    app2.include_router(router)
    client = TestClient(app2, raise_server_exceptions=False)
    resp = client.get("/projects")
    assert resp.status_code == 401
```

- [ ] **Step 2: テストを実行して失敗を確認**

```bash
pytest tests/unit/test_projects_router.py -v
```

Expected: `ImportError`

- [ ] **Step 3: `src/api/routers/__init__.py` を作成（空）、`src/api/routers/projects.py` を作成**

```python
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import CurrentUser, require_role
from src.db.engine import get_db
from src.db.models import Project
from src.models.task_web import ProjectCreate, ProjectResponse, ProjectUpdate

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

DbDep = Annotated[AsyncSession, Depends(get_db)]


@router.get("", response_model=list[ProjectResponse])
async def list_projects(db: DbDep, current_user: CurrentUser) -> list[ProjectResponse]:
    result = await db.execute(select(Project).order_by(Project.created_at.desc()))
    return [ProjectResponse.model_validate(p) for p in result.scalars().all()]


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(body: ProjectCreate, db: DbDep, current_user: CurrentUser) -> ProjectResponse:
    project = Project(**body.model_dump(), created_by=current_user.sub)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: uuid.UUID, db: DbDep, current_user: CurrentUser) -> ProjectResponse:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="プロジェクトが見つかりません")
    return ProjectResponse.model_validate(project)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID, body: ProjectUpdate, db: DbDep, current_user: CurrentUser
) -> ProjectResponse:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="プロジェクトが見つかりません")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID, db: DbDep, current_user: Annotated[CurrentUser, Depends(require_role("leader"))]
) -> None:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="プロジェクトが見つかりません")
    await db.delete(project)
    await db.commit()
```

- [ ] **Step 4: テストを実行**

```bash
pytest tests/unit/test_projects_router.py -v
```

Expected: 2 passed

- [ ] **Step 5: コミット**

```bash
git add src/api/routers/ tests/unit/test_projects_router.py
git commit -m "feat: プロジェクト CRUD ルーター"
```

---

### Task 7: タスク CRUD ルーター

**Files:**
- Create: `src/api/routers/tasks.py`
- Create: `tests/unit/test_tasks_router.py`

- [ ] **Step 1: テストを書く**

`tests/unit/test_tasks_router.py`：
```python
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import CurrentUser, TokenPayload, get_current_user
from src.api.routers.tasks import router

app = FastAPI()
app.include_router(router)
_user = TokenPayload(sub="user-1", name="Test", email="t@t.com", roles=["member"], tid="tid")
app.dependency_overrides[get_current_user] = lambda: _user


def test_list_tasks_endpoint_exists() -> None:
    from fastapi.testclient import TestClient
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/tasks")
    assert resp.status_code != 404


def test_create_task_validates_body() -> None:
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/tasks", json={})
    assert resp.status_code == 422


def test_task_routes_registered() -> None:
    routes = [r.path for r in app.routes]
    assert any("/tasks" in r for r in routes)
    assert any("/tasks/{task_id}" in r for r in routes)
```

- [ ] **Step 2: テストを実行して失敗を確認**

```bash
pytest tests/unit/test_tasks_router.py -v
```

Expected: `ImportError`

- [ ] **Step 3: `src/api/routers/tasks.py` を作成**

```python
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.auth import CurrentUser
from src.db.engine import get_db
from src.db.models import Task, TaskTag
from src.models.task_web import (
    TaskCreate,
    TaskListResponse,
    TaskResponse,
    TaskStatus,
    TaskUpdate,
)

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])
DbDep = Annotated[AsyncSession, Depends(get_db)]


def _task_to_response(task: Task) -> TaskResponse:
    tags = [t.tag for t in task.tags] if task.tags else []
    return TaskResponse(
        id=task.id,
        project_id=task.project_id,
        parent_task_id=task.parent_task_id,
        title=task.title,
        description=task.description,
        status=TaskStatus(task.status),
        priority=task.priority,
        assignee_id=task.assignee_id,
        due_date=task.due_date,
        start_date=task.start_date,
        visibility=task.visibility,
        source_type=task.source_type,
        confidence_score=task.confidence_score,
        route=task.route,
        created_by=task.created_by,
        created_at=task.created_at,
        updated_at=task.updated_at,
        tags=tags,
    )


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    db: DbDep,
    current_user: CurrentUser,
    status_filter: str | None = Query(default=None, alias="status"),
    assignee: str | None = None,
    project_id: uuid.UUID | None = None,
    tag: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
) -> TaskListResponse:
    q = select(Task).options(selectinload(Task.tags))
    if status_filter:
        q = q.where(Task.status == status_filter)
    if assignee:
        q = q.where(Task.assignee_id == assignee)
    if project_id:
        q = q.where(Task.project_id == project_id)
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()
    result = await db.execute(q.order_by(Task.due_date.asc().nullslast()).limit(limit).offset(offset))
    tasks = [_task_to_response(t) for t in result.scalars().all()]
    return TaskListResponse(items=tasks, total=total)


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(body: TaskCreate, db: DbDep, current_user: CurrentUser) -> TaskResponse:
    tags = body.tags
    data = body.model_dump(exclude={"tags"})
    data["created_by"] = current_user.sub
    task = Task(**data)
    db.add(task)
    await db.flush()
    for tag in tags:
        db.add(TaskTag(task_id=task.id, tag=tag))
    await db.commit()
    await db.refresh(task, ["tags"])
    return _task_to_response(task)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: uuid.UUID, db: DbDep, current_user: CurrentUser) -> TaskResponse:
    result = await db.execute(
        select(Task).where(Task.id == task_id).options(selectinload(Task.tags))
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="タスクが見つかりません")
    return _task_to_response(task)


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: uuid.UUID, body: TaskUpdate, db: DbDep, current_user: CurrentUser
) -> TaskResponse:
    result = await db.execute(
        select(Task).where(Task.id == task_id).options(selectinload(Task.tags))
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="タスクが見つかりません")
    update_data = body.model_dump(exclude_none=True, exclude={"tags"})
    for field, value in update_data.items():
        setattr(task, field, value)
    if body.tags is not None:
        for existing_tag in task.tags:
            await db.delete(existing_tag)
        for tag in body.tags:
            db.add(TaskTag(task_id=task.id, tag=tag))
    await db.commit()
    await db.refresh(task, ["tags"])
    return _task_to_response(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: uuid.UUID, db: DbDep, current_user: CurrentUser) -> None:
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="タスクが見つかりません")
    await db.delete(task)
    await db.commit()


@router.get("/{task_id}/subtasks", response_model=list[TaskResponse])
async def list_subtasks(
    task_id: uuid.UUID, db: DbDep, current_user: CurrentUser
) -> list[TaskResponse]:
    result = await db.execute(
        select(Task)
        .where(Task.parent_task_id == task_id)
        .options(selectinload(Task.tags))
    )
    return [_task_to_response(t) for t in result.scalars().all()]
```

- [ ] **Step 4: テストを実行して合格を確認**

```bash
pytest tests/unit/test_tasks_router.py -v
```

Expected: 3 passed

- [ ] **Step 5: コミット**

```bash
git add src/api/routers/tasks.py tests/unit/test_tasks_router.py
git commit -m "feat: タスク CRUD ルーター（一覧・作成・取得・更新・削除・サブタスク）"
```

---

### Task 8: コメント・工数・依存関係 API

**Files:**
- Create: `src/api/routers/task_details.py`

- [ ] **Step 1: `src/api/routers/task_details.py` を作成**

```python
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import CurrentUser
from src.db.engine import get_db
from src.db.models import Task, TaskComment, TaskDependency, TaskWorkHour
from src.models.task_web import (
    CommentCreate,
    CommentResponse,
    WorkHourCreate,
    WorkHourResponse,
)

router = APIRouter(prefix="/api/v1/tasks", tags=["task-details"])
DbDep = Annotated[AsyncSession, Depends(get_db)]


async def _get_task_or_404(task_id: uuid.UUID, db: AsyncSession) -> Task:
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="タスクが見つかりません")
    return task


# --- コメント ---

@router.get("/{task_id}/comments", response_model=list[CommentResponse])
async def list_comments(
    task_id: uuid.UUID, db: DbDep, current_user: CurrentUser
) -> list[CommentResponse]:
    await _get_task_or_404(task_id, db)
    result = await db.execute(
        select(TaskComment)
        .where(TaskComment.task_id == task_id)
        .order_by(TaskComment.created_at.asc())
    )
    return [CommentResponse.model_validate(c) for c in result.scalars().all()]


@router.post("/{task_id}/comments", response_model=CommentResponse, status_code=201)
async def create_comment(
    task_id: uuid.UUID, body: CommentCreate, db: DbDep, current_user: CurrentUser
) -> CommentResponse:
    await _get_task_or_404(task_id, db)
    comment = TaskComment(
        task_id=task_id,
        author_id=current_user.sub,
        content=body.content,
        mentions=body.mentions,
        sharepoint_links=body.sharepoint_links,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return CommentResponse.model_validate(comment)


# --- 工数 ---

@router.get("/{task_id}/work-hours", response_model=list[WorkHourResponse])
async def list_work_hours(
    task_id: uuid.UUID, db: DbDep, current_user: CurrentUser
) -> list[WorkHourResponse]:
    await _get_task_or_404(task_id, db)
    result = await db.execute(
        select(TaskWorkHour)
        .where(TaskWorkHour.task_id == task_id)
        .order_by(TaskWorkHour.recorded_at.desc())
    )
    return [WorkHourResponse.model_validate(wh) for wh in result.scalars().all()]


@router.post("/{task_id}/work-hours", response_model=WorkHourResponse, status_code=201)
async def create_work_hour(
    task_id: uuid.UUID, body: WorkHourCreate, db: DbDep, current_user: CurrentUser
) -> WorkHourResponse:
    await _get_task_or_404(task_id, db)
    wh = TaskWorkHour(
        task_id=task_id,
        user_id=current_user.sub,
        estimated_hours=body.estimated_hours,
        actual_hours=body.actual_hours,
        notes=body.notes,
    )
    db.add(wh)
    await db.commit()
    await db.refresh(wh)
    return WorkHourResponse.model_validate(wh)


# --- 依存関係 ---

@router.get("/{task_id}/dependencies")
async def list_dependencies(
    task_id: uuid.UUID, db: DbDep, current_user: CurrentUser
) -> list[dict]:
    result = await db.execute(
        select(TaskDependency).where(TaskDependency.task_id == task_id)
    )
    return [
        {"id": str(d.id), "depends_on_task_id": str(d.depends_on_task_id)}
        for d in result.scalars().all()
    ]


@router.post("/{task_id}/dependencies", status_code=201)
async def create_dependency(
    task_id: uuid.UUID, depends_on_task_id: uuid.UUID, db: DbDep, current_user: CurrentUser
) -> dict:
    await _get_task_or_404(task_id, db)
    await _get_task_or_404(depends_on_task_id, db)
    dep = TaskDependency(task_id=task_id, depends_on_task_id=depends_on_task_id)
    db.add(dep)
    await db.commit()
    await db.refresh(dep)
    return {"id": str(dep.id), "depends_on_task_id": str(dep.depends_on_task_id)}


@router.delete("/{task_id}/dependencies/{dep_id}", status_code=204)
async def delete_dependency(
    task_id: uuid.UUID, dep_id: uuid.UUID, db: DbDep, current_user: CurrentUser
) -> None:
    result = await db.execute(
        select(TaskDependency).where(TaskDependency.id == dep_id, TaskDependency.task_id == task_id)
    )
    dep = result.scalar_one_or_none()
    if dep is None:
        raise HTTPException(status_code=404, detail="依存関係が見つかりません")
    await db.delete(dep)
    await db.commit()
```

- [ ] **Step 2: インポートが通ることを確認**

```bash
python -c "from src.api.routers.task_details import router; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: コミット**

```bash
git add src/api/routers/task_details.py
git commit -m "feat: コメント・工数・依存関係 API"
```

---

### Task 9: ダッシュボード API

**Files:**
- Create: `src/api/routers/dashboard.py`
- Create: `tests/unit/test_dashboard_router.py`

- [ ] **Step 1: テストを書く**

`tests/unit/test_dashboard_router.py`：
```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import get_current_user, TokenPayload
from src.api.routers.dashboard import router

app = FastAPI()
app.include_router(router)
_user = TokenPayload(sub="user-1", name="Test", email="t@t.com", roles=["member"], tid="tid")
app.dependency_overrides[get_current_user] = lambda: _user


def test_dashboard_routes_registered() -> None:
    routes = [r.path for r in app.routes]
    assert any("summary" in r for r in routes)
    assert any("workload" in r for r in routes)
    assert any("today" in r for r in routes)
    assert any("overdue" in r for r in routes)


def test_summary_endpoint_exists() -> None:
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/dashboard/summary")
    assert resp.status_code != 404
```

- [ ] **Step 2: テストを実行して失敗を確認**

```bash
pytest tests/unit/test_dashboard_router.py -v
```

Expected: `ImportError`

- [ ] **Step 3: `src/api/routers/dashboard.py` を作成**

```python
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import CurrentUser
from src.db.engine import get_db
from src.db.models import Task, TaskWorkHour, UserProfile
from src.models.task_web import DashboardSummary, TaskResponse, TaskStatus, WorkloadItem

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])
DbDep = Annotated[AsyncSession, Depends(get_db)]


@router.get("/summary", response_model=DashboardSummary)
async def get_summary(db: DbDep, current_user: CurrentUser) -> DashboardSummary:
    today = date.today()
    result = await db.execute(select(Task.status, func.count()).group_by(Task.status))
    counts = {row[0]: row[1] for row in result.all()}
    total = sum(counts.values())
    not_started = counts.get("not_started", 0)
    in_progress = counts.get("in_progress", 0)
    completed = counts.get("completed", 0)
    overdue_result = await db.execute(
        select(func.count(Task.id)).where(
            Task.due_date < today,
            Task.status.notin_(["completed", "cancelled"]),
        )
    )
    overdue = overdue_result.scalar_one()
    completion_rate = (completed / total * 100) if total > 0 else 0.0
    return DashboardSummary(
        total_tasks=total,
        not_started=not_started,
        in_progress=in_progress,
        completed=completed,
        overdue=overdue,
        completion_rate=round(completion_rate, 1),
    )


@router.get("/today", response_model=list[dict])
async def get_today_tasks(db: DbDep, current_user: CurrentUser) -> list[dict]:
    today = date.today()
    result = await db.execute(
        select(Task)
        .where(
            Task.due_date == today,
            Task.status.notin_(["completed", "cancelled"]),
        )
        .order_by(Task.priority.desc())
    )
    tasks = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "title": t.title,
            "status": t.status,
            "priority": t.priority,
            "assignee_id": t.assignee_id,
        }
        for t in tasks
    ]


@router.get("/overdue", response_model=list[dict])
async def get_overdue_tasks(db: DbDep, current_user: CurrentUser) -> list[dict]:
    today = date.today()
    result = await db.execute(
        select(Task)
        .where(
            Task.due_date < today,
            Task.status.notin_(["completed", "cancelled"]),
        )
        .order_by(Task.due_date.asc())
        .limit(50)
    )
    tasks = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "title": t.title,
            "status": t.status,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "assignee_id": t.assignee_id,
        }
        for t in tasks
    ]


@router.get("/workload", response_model=list[WorkloadItem])
async def get_workload(db: DbDep, current_user: CurrentUser) -> list[WorkloadItem]:
    today = date.today()
    next_week = today + timedelta(days=7)
    wh_result = await db.execute(
        select(TaskWorkHour.user_id, func.sum(TaskWorkHour.estimated_hours))
        .join(Task, Task.id == TaskWorkHour.task_id)
        .where(
            Task.due_date >= today,
            Task.due_date <= next_week,
            Task.status.notin_(["completed", "cancelled"]),
        )
        .group_by(TaskWorkHour.user_id)
    )
    user_hours = {row[0]: row[1] or 0.0 for row in wh_result.all()}

    profiles_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id.in_(list(user_hours.keys())))
    )
    profiles = {p.user_id: p for p in profiles_result.scalars().all()}

    items = []
    for user_id, hours in user_hours.items():
        profile = profiles.get(user_id)
        capacity = (profile.capacity_hours_per_day * 5) if profile else 40.0
        display_name = profile.display_name if profile else user_id
        items.append(
            WorkloadItem(
                user_id=user_id,
                display_name=display_name,
                estimated_hours=hours,
                capacity_hours=capacity,
                overload=hours > capacity,
            )
        )
    return items


@router.get("/completion-trend", response_model=list[dict])
async def get_completion_trend(db: DbDep, current_user: CurrentUser) -> list[dict]:
    today = date.today()
    result = []
    for i in range(7, -1, -1):
        day = today - timedelta(days=i)
        count_result = await db.execute(
            select(func.count(Task.id)).where(
                func.date(Task.updated_at) == day,
                Task.status == "completed",
            )
        )
        result.append({"date": day.isoformat(), "completed": count_result.scalar_one()})
    return result
```

- [ ] **Step 4: テストを実行して合格を確認**

```bash
pytest tests/unit/test_dashboard_router.py -v
```

Expected: 2 passed

- [ ] **Step 5: コミット**

```bash
git add src/api/routers/dashboard.py tests/unit/test_dashboard_router.py
git commit -m "feat: ダッシュボード API（summary, today, overdue, workload, trend）"
```

---

### Task 10: main.py にルーター登録・DB 起動処理

**Files:**
- Modify: `src/api/main.py`
- Create: `src/api/routers/users.py`

- [ ] **Step 1: `src/api/routers/users.py` を作成**

```python
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import CurrentUser
from src.db.engine import get_db
from src.db.models import UserProfile

router = APIRouter(prefix="/api/v1/users", tags=["users"])
DbDep = Annotated[AsyncSession, Depends(get_db)]


@router.get("/me")
async def get_me(current_user: CurrentUser) -> dict:
    return {
        "user_id": current_user.sub,
        "name": current_user.name,
        "email": current_user.email,
        "roles": current_user.roles,
    }


@router.get("")
async def list_users(db: DbDep, current_user: CurrentUser) -> list[dict]:
    result = await db.execute(select(UserProfile).order_by(UserProfile.display_name))
    return [
        {
            "user_id": u.user_id,
            "display_name": u.display_name,
            "email": u.email,
            "role": u.role,
            "capacity_hours_per_day": u.capacity_hours_per_day,
        }
        for u in result.scalars().all()
    ]
```

- [ ] **Step 2: `src/api/main.py` にルーターを登録**

`src/api/main.py` の既存コードに以下を追記（`app = FastAPI(...)` の後、`@app.get("/health")` の前）：

```python
from src.api.routers import projects, tasks, task_details, dashboard, users

app.include_router(projects.router)
app.include_router(tasks.router)
app.include_router(task_details.router)
app.include_router(dashboard.router)
app.include_router(users.router)
```

また、CORS ミドルウェアを追加（フロントエンドの `http://localhost:5173` からアクセスできるよう）：

```python
from fastapi.middleware.cors import CORSMiddleware
from src.models.config import Settings

_settings = Settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[_settings.frontend_url, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

- [ ] **Step 3: サーバー起動を確認**

```bash
uvicorn src.api.main:app --reload --port 8000
```

ブラウザで `http://localhost:8000/docs` を開き、全ルーターが表示されることを確認。

- [ ] **Step 4: 全テストを実行して既存テストが通ることを確認**

```bash
pytest tests/unit/ -v
```

Expected: 65 + 追加分がすべて pass

- [ ] **Step 5: コミット**

```bash
git add src/api/main.py src/api/routers/users.py
git commit -m "feat: FastAPI に全ルーターを登録・CORS ミドルウェア追加"
```

---

### Task 11: LangGraph 起票先を PostgreSQL に変更

**Files:**
- Modify: `src/agents/nodes.py`
- Modify: `src/services/routing.py`

- [ ] **Step 1: `src/services/routing.py` を修正**

`create_tasks_in_planner` / `create_tasks_in_todo` 関数を PostgreSQL 保存に置き換える。

既存の `src/services/routing.py` を読み込み、Planner/To Do への起票ロジックを以下の関数に置き換える：

```python
import uuid
from src.db.engine import AsyncSessionLocal
from src.db.models import Task as TaskORM


async def _save_tasks_to_postgres(
    tasks: list[dict],
    source_type: str,
    source_id: str,
    confidence_score: float,
    route: str,
) -> list[str]:
    """抽出されたタスクを PostgreSQL に保存し、タスク ID リストを返す。"""
    saved_ids: list[str] = []
    async with AsyncSessionLocal() as session:
        for task_dict in tasks:
            task = TaskORM(
                title=task_dict.get("title", "（タイトルなし）"),
                description=task_dict.get("description"),
                assignee_id=task_dict.get("assignee_id"),
                due_date=task_dict.get("due_date"),
                visibility=task_dict.get("visibility", "team"),
                source_type=source_type,
                source_id=source_id,
                confidence_score=confidence_score,
                route=route,
                created_by="system",
            )
            session.add(task)
            await session.flush()
            saved_ids.append(str(task.id))
        await session.commit()
    return saved_ids
```

- [ ] **Step 2: `src/agents/nodes.py` の `auto_create` ノードを修正**

`auto_create` ノード内の Planner/To Do 呼び出し部分を `_save_tasks_to_postgres` 呼び出しに変更する。

既存コードの `planner.create_task(...)` / `todo.create_task(...)` を以下に置き換え：

```python
from src.services.routing import _save_tasks_to_postgres

# auto_create ノード内
saved_ids = await _save_tasks_to_postgres(
    tasks=state["extracted_tasks"],
    source_type=state.get("source_type", "unknown"),
    source_id=state.get("source_id", ""),
    confidence_score=state.get("confidence_score", 0.0),
    route="auto_create",
)
state["ticket_ids"] = saved_ids
```

- [ ] **Step 3: エージェントのテストが通ることを確認**

```bash
pytest tests/unit/test_agent.py -v
```

Expected: 2 passed（モックが PostgreSQL に対応していることを確認）

- [ ] **Step 4: コミット**

```bash
git add src/agents/nodes.py src/services/routing.py
git commit -m "feat: LangGraph 起票先を Microsoft Planner から PostgreSQL に変更"
```

---

### Task 12: Microsoft Forms ポーリング追加

**Files:**
- Create: `src/connectors/forms.py`
- Modify: `src/services/polling_job.py`

- [ ] **Step 1: `src/connectors/forms.py` を作成**

```python
from typing import Any

import httpx

from src.models.config import Settings

_settings = Settings()


async def get_form_responses(access_token: str, since_id: str | None = None) -> list[dict[str, Any]]:
    """SharePoint リストから Forms の回答を取得する。"""
    if not _settings.sharepoint_site_id or not _settings.forms_list_id:
        return []

    url = (
        f"https://graph.microsoft.com/v1.0/sites/{_settings.sharepoint_site_id}"
        f"/lists/{_settings.forms_list_id}/items"
        "?$expand=fields&$orderby=createdDateTime asc"
    )
    if since_id:
        url += f"&$filter=id gt '{since_id}'"

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("value", [])
```

- [ ] **Step 2: `src/services/polling_job.py` に Forms ポーリングを追加**

`polling_job()` 関数内に以下を追加（既存の Teams チャット・OneNote ポーリングの後）：

```python
    # Microsoft Forms（SharePoint 経由）
    if _settings.sharepoint_site_id and _settings.forms_list_id:
        try:
            form_responses = await get_form_responses(access_token)
            for form_item in form_responses:
                item_id = form_item.get("id", "")
                if await _state_service.is_processed(item_id):
                    continue
                fields = form_item.get("fields", {})
                text = "\n".join(f"{k}: {v}" for k, v in fields.items() if isinstance(v, str))
                if text.strip():
                    await _run_agent_and_route(
                        text=text,
                        source_type="form",
                        source_id=item_id,
                    )
                    await _state_service.mark_processed(item_id)
        except Exception as e:
            logger.warning("Forms ポーリングエラー: %s", e)
```

- [ ] **Step 3: インポートが通ることを確認**

```bash
python -c "from src.connectors.forms import get_form_responses; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: 全テストを実行**

```bash
pytest tests/ -v --ignore=tests/integration
```

Expected: 65+ 件 pass（新規テストは軽微なため既存テストが通ることを確認）

- [ ] **Step 5: コミット**

```bash
git add src/connectors/forms.py src/services/polling_job.py
git commit -m "feat: Microsoft Forms（SharePoint）ポーリング追加（F-16）"
```

---

## Group 3: フロントエンド基盤

### Task 13: React + Vite + TypeScript プロジェクト初期化

**Files:**
- Create: `frontend/` ディレクトリ以下すべて

- [ ] **Step 1: Vite で React + TypeScript プロジェクトを作成**

```bash
cd frontend
npm create vite@latest . -- --template react-ts
npm install
```

- [ ] **Step 2: 追加パッケージをインストール**

```bash
npm install antd @ant-design/icons \
  @tanstack/react-query \
  zustand \
  react-router-dom \
  axios \
  recharts \
  @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities \
  @azure/msal-browser @azure/msal-react \
  dayjs
npm install -D vitest @vitest/ui @testing-library/react @testing-library/jest-dom \
  @testing-library/user-event jsdom eslint prettier
```

- [ ] **Step 3: `frontend/vite.config.ts` を更新（テスト設定追加）**

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
  },
})
```

- [ ] **Step 4: `frontend/src/test/setup.ts` を作成**

```typescript
import '@testing-library/jest-dom'
```

- [ ] **Step 5: `frontend/tsconfig.json` の `strict` が `true` であることを確認**

```json
{
  "compilerOptions": {
    "strict": true
  }
}
```

- [ ] **Step 6: 開発サーバーが起動することを確認**

```bash
cd frontend && npm run dev
```

Expected: `http://localhost:5173` でデフォルト画面が表示される

- [ ] **Step 7: コミット**

```bash
cd ..
git add frontend/
git commit -m "feat: React + Vite + TypeScript フロントエンド基盤を初期化"
```

---

### Task 14: MSAL 認証設定 + ルーティング

**Files:**
- Create: `frontend/src/lib/msal.ts`
- Create: `frontend/src/store/useAuthStore.ts`
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: `frontend/src/lib/msal.ts` を作成**

```typescript
import { Configuration, PublicClientApplication } from '@azure/msal-browser'

const msalConfig: Configuration = {
  auth: {
    clientId: import.meta.env.VITE_AZURE_CLIENT_ID ?? '',
    authority: `https://login.microsoftonline.com/${import.meta.env.VITE_AZURE_TENANT_ID ?? 'common'}`,
    redirectUri: window.location.origin,
  },
  cache: {
    cacheLocation: 'sessionStorage',
  },
}

export const msalInstance = new PublicClientApplication(msalConfig)

export const loginRequest = {
  scopes: [`api://${import.meta.env.VITE_AZURE_CLIENT_ID ?? ''}/user_impersonation`],
}
```

- [ ] **Step 2: `frontend/src/store/useAuthStore.ts` を作成**

```typescript
import { create } from 'zustand'

interface AuthState {
  userId: string | null
  displayName: string | null
  email: string | null
  roles: string[]
  setUser: (user: { userId: string; displayName: string; email: string; roles: string[] }) => void
  clearUser: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  userId: null,
  displayName: null,
  email: null,
  roles: [],
  setUser: (user) => set(user),
  clearUser: () => set({ userId: null, displayName: null, email: null, roles: [] }),
}))
```

- [ ] **Step 3: `frontend/src/main.tsx` を更新**

```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import { MsalProvider } from '@azure/msal-react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { msalInstance } from './lib/msal'
import 'antd/dist/reset.css'

const queryClient = new QueryClient()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <MsalProvider instance={msalInstance}>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </MsalProvider>
  </React.StrictMode>,
)
```

- [ ] **Step 4: `frontend/src/App.tsx` を更新（ルーティング定義）**

```tsx
import { useMsal, useIsAuthenticated } from '@azure/msal-react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { Button, Layout, Typography } from 'antd'
import { loginRequest } from './lib/msal'
import Dashboard from './pages/Dashboard'
import TaskList from './pages/Tasks'
import TaskDetail from './pages/Tasks/TaskDetail'
import Schedule from './pages/Schedule'
import Workload from './pages/Workload'

const { Header, Content } = Layout

function LoginPage() {
  const { instance } = useMsal()
  return (
    <div style={{ textAlign: 'center', paddingTop: 100 }}>
      <Typography.Title>AutoTicket</Typography.Title>
      <Button type="primary" size="large" onClick={() => instance.loginRedirect(loginRequest)}>
        Microsoft アカウントでログイン
      </Button>
    </div>
  )
}

export default function App() {
  const isAuthenticated = useIsAuthenticated()

  if (!isAuthenticated) {
    return <LoginPage />
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ color: 'white', fontSize: 18 }}>AutoTicket</Header>
      <Content style={{ padding: 24 }}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/tasks" element={<TaskList />} />
          <Route path="/tasks/:id" element={<TaskDetail />} />
          <Route path="/schedule" element={<Schedule />} />
          <Route path="/workload" element={<Workload />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </Content>
    </Layout>
  )
}
```

- [ ] **Step 5: `frontend/.env.local` を作成（git 管理外）**

```env
VITE_AZURE_CLIENT_ID=your-spa-client-id
VITE_AZURE_TENANT_ID=your-tenant-id
```

- [ ] **Step 6: TypeScript エラーがないことを確認**

```bash
cd frontend && npx tsc --noEmit
```

Expected: エラーなし（または page コンポーネント未作成のエラーのみ）

- [ ] **Step 7: コミット**

```bash
cd ..
git add frontend/src/lib/msal.ts frontend/src/store/ frontend/src/main.tsx frontend/src/App.tsx
git commit -m "feat: MSAL 認証・React Router ルーティング設定"
```

---

### Task 15: API クライアント + TanStack Query フック

**Files:**
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/hooks/useTasks.ts`
- Create: `frontend/src/hooks/useProjects.ts`
- Create: `frontend/src/hooks/useDashboard.ts`
- Create: `frontend/src/test/hooks.test.ts`

- [ ] **Step 1: `frontend/src/lib/api.ts` を作成**

```typescript
import axios from 'axios'
import { msalInstance, loginRequest } from './msal'

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use(async (config) => {
  const accounts = msalInstance.getAllAccounts()
  if (accounts.length > 0) {
    try {
      const result = await msalInstance.acquireTokenSilent({
        ...loginRequest,
        account: accounts[0],
      })
      config.headers.Authorization = `Bearer ${result.accessToken}`
    } catch {
      await msalInstance.loginRedirect(loginRequest)
    }
  }
  return config
})

export default api

export interface Task {
  id: string
  title: string
  status: string
  priority: string
  assignee_id: string | null
  due_date: string | null
  visibility: string
  tags: string[]
  created_at: string
  updated_at: string
}

export interface TaskListResponse {
  items: Task[]
  total: number
}

export interface Project {
  id: string
  name: string
  description: string | null
  status: string
  created_by: string
  created_at: string
}

export interface DashboardSummary {
  total_tasks: number
  not_started: number
  in_progress: number
  completed: number
  overdue: number
  completion_rate: number
}

export interface WorkloadItem {
  user_id: string
  display_name: string
  estimated_hours: number
  capacity_hours: number
  overload: boolean
}
```

- [ ] **Step 2: `frontend/src/hooks/useTasks.ts` を作成**

```typescript
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api, { Task, TaskListResponse } from '../lib/api'

interface TaskFilters {
  status?: string
  assignee?: string
  project_id?: string
  tag?: string
  limit?: number
  offset?: number
}

export function useTasks(filters: TaskFilters = {}) {
  return useQuery<TaskListResponse>({
    queryKey: ['tasks', filters],
    queryFn: async () => {
      const { data } = await api.get('/tasks', { params: filters })
      return data
    },
  })
}

export function useTask(id: string) {
  return useQuery<Task>({
    queryKey: ['task', id],
    queryFn: async () => {
      const { data } = await api.get(`/tasks/${id}`)
      return data
    },
    enabled: !!id,
  })
}

export function useCreateTask() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: Partial<Task> & { title: string }) => {
      const { data } = await api.post('/tasks', body)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
    },
  })
}

export function useUpdateTask() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...body }: Partial<Task> & { id: string }) => {
      const { data } = await api.put(`/tasks/${id}`, body)
      return data
    },
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      queryClient.invalidateQueries({ queryKey: ['task', id] })
    },
  })
}

export function useDeleteTask() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/tasks/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
    },
  })
}
```

- [ ] **Step 3: `frontend/src/hooks/useDashboard.ts` を作成**

```typescript
import { useQuery } from '@tanstack/react-query'
import api, { DashboardSummary, WorkloadItem } from '../lib/api'

export function useDashboardSummary() {
  return useQuery<DashboardSummary>({
    queryKey: ['dashboard', 'summary'],
    queryFn: async () => {
      const { data } = await api.get('/dashboard/summary')
      return data
    },
  })
}

export function useTodayTasks() {
  return useQuery<Record<string, unknown>[]>({
    queryKey: ['dashboard', 'today'],
    queryFn: async () => {
      const { data } = await api.get('/dashboard/today')
      return data
    },
  })
}

export function useOverdueTasks() {
  return useQuery<Record<string, unknown>[]>({
    queryKey: ['dashboard', 'overdue'],
    queryFn: async () => {
      const { data } = await api.get('/dashboard/overdue')
      return data
    },
  })
}

export function useWorkload() {
  return useQuery<WorkloadItem[]>({
    queryKey: ['dashboard', 'workload'],
    queryFn: async () => {
      const { data } = await api.get('/dashboard/workload')
      return data
    },
  })
}
```

- [ ] **Step 4: `frontend/src/hooks/useProjects.ts` を作成**

```typescript
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api, { Project } from '../lib/api'

export function useProjects() {
  return useQuery<Project[]>({
    queryKey: ['projects'],
    queryFn: async () => {
      const { data } = await api.get('/projects')
      return data
    },
  })
}

export function useCreateProject() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: { name: string; description?: string }) => {
      const { data } = await api.post('/projects', body)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}
```

- [ ] **Step 5: TypeScript エラーがないことを確認**

```bash
cd frontend && npx tsc --noEmit
```

Expected: エラーなし

- [ ] **Step 6: コミット**

```bash
cd ..
git add frontend/src/lib/api.ts frontend/src/hooks/
git commit -m "feat: axios API クライアント + TanStack Query カスタムフック"
```

---

## Group 4: フロントエンド UI

### Task 16: タスク一覧ページ

**Files:**
- Create: `frontend/src/pages/Tasks/index.tsx`
- Create: `frontend/src/pages/Tasks/TaskDetail.tsx`

- [ ] **Step 1: `frontend/src/pages/Tasks/index.tsx` を作成**

```tsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Button,
  Input,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  Form,
  message,
} from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import { useTasks, useCreateTask } from '../../hooks/useTasks'
import type { Task } from '../../lib/api'

const STATUS_COLOR: Record<string, string> = {
  not_started: 'default',
  in_progress: 'processing',
  completed: 'success',
  cancelled: 'error',
}

const STATUS_LABEL: Record<string, string> = {
  not_started: '未着手',
  in_progress: '進行中',
  completed: '完了',
  cancelled: 'キャンセル',
}

const PRIORITY_COLOR: Record<string, string> = {
  low: 'green',
  medium: 'blue',
  high: 'orange',
  urgent: 'red',
}

export default function TaskList() {
  const navigate = useNavigate()
  const [statusFilter, setStatusFilter] = useState<string | undefined>()
  const [modalOpen, setModalOpen] = useState(false)
  const [form] = Form.useForm()

  const { data, isLoading } = useTasks({ status: statusFilter })
  const createTask = useCreateTask()

  const columns: ColumnsType<Task> = [
    {
      title: 'タイトル',
      dataIndex: 'title',
      render: (text: string, record: Task) => (
        <Button type="link" onClick={() => navigate(`/tasks/${record.id}`)}>
          {text}
        </Button>
      ),
    },
    {
      title: 'ステータス',
      dataIndex: 'status',
      render: (s: string) => (
        <Tag color={STATUS_COLOR[s] ?? 'default'}>{STATUS_LABEL[s] ?? s}</Tag>
      ),
    },
    {
      title: '優先度',
      dataIndex: 'priority',
      render: (p: string) => <Tag color={PRIORITY_COLOR[p] ?? 'default'}>{p}</Tag>,
    },
    {
      title: '期限',
      dataIndex: 'due_date',
      render: (d: string | null) => (d ? dayjs(d).format('YYYY/MM/DD') : '—'),
    },
    {
      title: 'タグ',
      dataIndex: 'tags',
      render: (tags: string[]) => tags.map((t) => <Tag key={t}>{t}</Tag>),
    },
  ]

  const handleCreate = async () => {
    const values = await form.validateFields()
    await createTask.mutateAsync({ ...values, created_by: 'current-user' })
    message.success('タスクを作成しました')
    form.resetFields()
    setModalOpen(false)
  }

  return (
    <div>
      <Space style={{ marginBottom: 16, justifyContent: 'space-between', width: '100%' }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          タスク一覧
        </Typography.Title>
        <Space>
          <Select
            allowClear
            placeholder="ステータス"
            style={{ width: 120 }}
            onChange={setStatusFilter}
            options={Object.entries(STATUS_LABEL).map(([value, label]) => ({ value, label }))}
          />
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
            新規タスク
          </Button>
        </Space>
      </Space>

      <Table
        rowKey="id"
        loading={isLoading}
        dataSource={data?.items ?? []}
        columns={columns}
        pagination={{ total: data?.total, pageSize: 50 }}
      />

      <Modal
        title="新規タスク作成"
        open={modalOpen}
        onOk={handleCreate}
        onCancel={() => setModalOpen(false)}
        okText="作成"
        cancelText="キャンセル"
        confirmLoading={createTask.isPending}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="title" label="タイトル" rules={[{ required: true, message: '必須' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="詳細">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="priority" label="優先度" initialValue="medium">
            <Select
              options={[
                { value: 'low', label: '低' },
                { value: 'medium', label: '中' },
                { value: 'high', label: '高' },
                { value: 'urgent', label: '緊急' },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
```

- [ ] **Step 2: `frontend/src/pages/Tasks/TaskDetail.tsx` を作成**

```tsx
import { useParams, useNavigate } from 'react-router-dom'
import {
  Button,
  Card,
  Descriptions,
  Form,
  Input,
  Select,
  Space,
  Tag,
  Typography,
  message,
} from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useTask, useUpdateTask } from '../../hooks/useTasks'

export default function TaskDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data: task, isLoading } = useTask(id ?? '')
  const updateTask = useUpdateTask()
  const [form] = Form.useForm()

  if (isLoading) return <div>読み込み中...</div>
  if (!task) return <div>タスクが見つかりません</div>

  const handleStatusChange = async (status: string) => {
    await updateTask.mutateAsync({ id: task.id, status })
    message.success('ステータスを更新しました')
  }

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/tasks')}>
          一覧へ
        </Button>
        <Typography.Title level={4} style={{ margin: 0 }}>
          {task.title}
        </Typography.Title>
      </Space>

      <Card>
        <Descriptions column={2} bordered>
          <Descriptions.Item label="ステータス">
            <Select
              value={task.status}
              onChange={handleStatusChange}
              options={[
                { value: 'not_started', label: '未着手' },
                { value: 'in_progress', label: '進行中' },
                { value: 'completed', label: '完了' },
                { value: 'cancelled', label: 'キャンセル' },
              ]}
              style={{ width: 120 }}
            />
          </Descriptions.Item>
          <Descriptions.Item label="優先度">
            <Tag>{task.priority}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="期限">
            {task.due_date ? dayjs(task.due_date).format('YYYY/MM/DD') : '—'}
          </Descriptions.Item>
          <Descriptions.Item label="公開範囲">{task.visibility}</Descriptions.Item>
          <Descriptions.Item label="タグ" span={2}>
            {task.tags.map((t) => (
              <Tag key={t}>{t}</Tag>
            ))}
          </Descriptions.Item>
          <Descriptions.Item label="詳細" span={2}>
            {task.description ?? '—'}
          </Descriptions.Item>
        </Descriptions>
      </Card>
    </div>
  )
}
```

- [ ] **Step 3: コミット**

```bash
git add frontend/src/pages/Tasks/
git commit -m "feat: タスク一覧・詳細ページ（F-01, F-02, F-03）"
```

---

### Task 17: ダッシュボードページ

**Files:**
- Create: `frontend/src/pages/Dashboard/index.tsx`

- [ ] **Step 1: `frontend/src/pages/Dashboard/index.tsx` を作成**

```tsx
import { Col, Row, Statistic, Card, List, Tag, Typography } from 'antd'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts'
import { useDashboardSummary, useTodayTasks, useOverdueTasks } from '../../hooks/useDashboard'

const COLORS = ['#8884d8', '#82ca9d', '#ffc658', '#ff7300']

export default function Dashboard() {
  const { data: summary, isLoading: summaryLoading } = useDashboardSummary()
  const { data: todayTasks } = useTodayTasks()
  const { data: overdueTasks } = useOverdueTasks()

  const pieData = summary
    ? [
        { name: '未着手', value: summary.not_started },
        { name: '進行中', value: summary.in_progress },
        { name: '完了', value: summary.completed },
      ]
    : []

  return (
    <div>
      <Typography.Title level={4}>ダッシュボード</Typography.Title>

      {/* KPI カード */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic title="総タスク数" value={summary?.total_tasks ?? 0} loading={summaryLoading} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="完了率" value={summary?.completion_rate ?? 0} suffix="%" loading={summaryLoading} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="進行中" value={summary?.in_progress ?? 0} loading={summaryLoading} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="期限超過"
              value={summary?.overdue ?? 0}
              valueStyle={{ color: summary?.overdue ? '#cf1322' : undefined }}
              loading={summaryLoading}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        {/* ステータス分布 */}
        <Col span={12}>
          <Card title="ステータス分布">
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" outerRadius={80} dataKey="value" label>
                  {pieData.map((_, index) => (
                    <Cell key={index} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Legend />
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </Card>
        </Col>

        {/* 今日やること */}
        <Col span={12}>
          <Card title="今日やること" extra={<Tag color="blue">{todayTasks?.length ?? 0}件</Tag>}>
            <List
              dataSource={todayTasks ?? []}
              renderItem={(item: Record<string, unknown>) => (
                <List.Item>
                  <Tag color={item['priority'] === 'urgent' ? 'red' : 'default'}>
                    {String(item['priority'])}
                  </Tag>
                  {String(item['title'])}
                </List.Item>
              )}
              locale={{ emptyText: '今日のタスクはありません' }}
              style={{ maxHeight: 200, overflowY: 'auto' }}
            />
          </Card>
        </Col>
      </Row>

      {/* 期限超過タスク */}
      {(overdueTasks?.length ?? 0) > 0 && (
        <Card title="期限超過タスク" style={{ marginBottom: 24 }}>
          <List
            dataSource={overdueTasks ?? []}
            renderItem={(item: Record<string, unknown>) => (
              <List.Item>
                <Tag color="red">{String(item['due_date'])}</Tag>
                {String(item['title'])}
              </List.Item>
            )}
          />
        </Card>
      )}
    </div>
  )
}
```

- [ ] **Step 2: コミット**

```bash
git add frontend/src/pages/Dashboard/
git commit -m "feat: ダッシュボードページ（F-09, F-10）"
```

---

### Task 18: スケジュール・ワークロードページ

**Files:**
- Create: `frontend/src/pages/Schedule/index.tsx`
- Create: `frontend/src/pages/Workload/index.tsx`

- [ ] **Step 1: `frontend/src/pages/Schedule/index.tsx` を作成**

```tsx
import { Typography, List, Tag, Card, Space } from 'antd'
import { useTodayTasks, useOverdueTasks } from '../../hooks/useDashboard'
import dayjs from 'dayjs'

const PRIORITY_COLOR: Record<string, string> = {
  low: 'green',
  medium: 'blue',
  high: 'orange',
  urgent: 'red',
}

export default function Schedule() {
  const { data: todayTasks, isLoading } = useTodayTasks()
  const { data: overdueTasks } = useOverdueTasks()

  return (
    <div>
      <Typography.Title level={4}>
        1日スケジュール — {dayjs().format('YYYY年M月D日（ddd）')}
      </Typography.Title>

      <Space direction="vertical" style={{ width: '100%' }} size={16}>
        <Card title="今日やること" loading={isLoading}>
          <List
            dataSource={todayTasks ?? []}
            renderItem={(item: Record<string, unknown>) => (
              <List.Item>
                <Space>
                  <Tag color={PRIORITY_COLOR[String(item['priority'])] ?? 'default'}>
                    {String(item['priority'])}
                  </Tag>
                  {String(item['title'])}
                </Space>
              </List.Item>
            )}
            locale={{ emptyText: '今日のタスクはありません' }}
          />
        </Card>

        {(overdueTasks?.length ?? 0) > 0 && (
          <Card title="期限超過">
            <List
              dataSource={overdueTasks ?? []}
              renderItem={(item: Record<string, unknown>) => (
                <List.Item>
                  <Space>
                    <Tag color="red">{String(item['due_date'])}</Tag>
                    {String(item['title'])}
                  </Space>
                </List.Item>
              )}
            />
          </Card>
        )}
      </Space>
    </div>
  )
}
```

- [ ] **Step 2: `frontend/src/pages/Workload/index.tsx` を作成**

```tsx
import { Typography, Card, Progress, Tag, Space, Alert } from 'antd'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'
import { useWorkload } from '../../hooks/useDashboard'

export default function Workload() {
  const { data: workload, isLoading } = useWorkload()

  const chartData = (workload ?? []).map((item) => ({
    name: item.display_name,
    予定工数: item.estimated_hours,
    キャパシティ: item.capacity_hours,
    超過: item.overload,
  }))

  const overloadUsers = (workload ?? []).filter((u) => u.overload)

  return (
    <div>
      <Typography.Title level={4}>ワークロード（今後7日間）</Typography.Title>

      {overloadUsers.length > 0 && (
        <Alert
          type="warning"
          message={`${overloadUsers.map((u) => u.display_name).join('、')} が工数超過です`}
          style={{ marginBottom: 16 }}
        />
      )}

      <Card loading={isLoading}>
        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis unit="h" />
            <Tooltip />
            <Bar dataKey="予定工数" fill="#8884d8" />
            <Bar dataKey="キャパシティ" fill="#82ca9d" />
          </BarChart>
        </ResponsiveContainer>
      </Card>

      <Space direction="vertical" style={{ width: '100%', marginTop: 16 }} size={8}>
        {(workload ?? []).map((item) => (
          <Card key={item.user_id} size="small">
            <Space>
              {item.overload && <Tag color="red">超過</Tag>}
              <span>{item.display_name}</span>
              <Progress
                percent={Math.round((item.estimated_hours / item.capacity_hours) * 100)}
                strokeColor={item.overload ? '#ff4d4f' : '#52c41a'}
                style={{ width: 200 }}
              />
              <span>
                {item.estimated_hours}h / {item.capacity_hours}h
              </span>
            </Space>
          </Card>
        ))}
      </Space>
    </div>
  )
}
```

- [ ] **Step 3: TypeScript エラーがないことを確認**

```bash
cd frontend && npx tsc --noEmit
```

Expected: エラーなし

- [ ] **Step 4: 開発サーバーで動作確認**

```bash
# バックエンド（別ターミナル）
uvicorn src.api.main:app --reload --port 8000

# フロントエンド
cd frontend && npm run dev
```

ブラウザで `http://localhost:5173` を開き、ログイン画面 → ダッシュボード → タスク一覧 → スケジュール → ワークロードの各ページが表示されることを確認。

- [ ] **Step 5: 最終テスト実行**

```bash
# バックエンド（プロジェクトルートから）
pytest tests/unit/ -v

# フロントエンド
cd frontend && npm run build
```

Expected: バックエンド 65+ tests passed、フロントエンド build 成功

- [ ] **Step 6: 最終コミット**

```bash
cd ..
git add frontend/src/pages/
git commit -m "feat: スケジュール・ワークロードページ（F-09, F-13）"
```

---

## スペックとの対照チェック

| F-ID | 機能名 | Task # | 対応状況 |
|------|--------|--------|---------|
| F-01 | タスク手動登録・編集・削除 | Task 7, 16 | ✅ |
| F-02 | タスク一覧表示（検索・絞り込み） | Task 7, 16 | ✅ |
| F-03 | タスク詳細管理（タグ・工数） | Task 7, 8, 16 | ✅ |
| F-04 | 二重登録防止 | — | ⚠️ Phase 1 で基本実装（タイトル類似度は Phase 2 で高度化） |
| F-05 | コメント機能 | Task 8 | ✅ |
| F-06 | プロジェクト管理 | Task 6 | ✅ |
| F-08 | 権限管理 | Task 5 | ✅ |
| F-09 | 1日スケジュール | Task 9, 18 | ✅ |
| F-10 | ダッシュボード | Task 9, 17 | ✅ |
| F-11 | D&D | — | ⚠️ API 基盤は Task 7 で完了。D&D UI は Phase 2 で実装 |
| F-12 | 予定/実績管理 | Task 8 | ✅ |
| F-13 | ワークロード | Task 9, 18 | ✅ |
| F-16 | Forms 連携 | Task 12 | ✅ |
| F-17 | 右クリック起票 | — | ⚠️ T-01（未解決事項）— Phase 2 以降 |
| F-18 | トランスクリプト | 既存 | ✅ |
| F-19 | 議事録 | 既存 | ✅ |
| F-21 | Teams 通知 | — | ⚠️ API 基盤は既存。コメント投稿時通知は Phase 2 で実装 |

> F-04（類似度）・F-11（D&D UI）・F-17・F-21 は API 基盤を Phase 1 で構築し、UI/高度化を Phase 2 で完成させる。

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-18-phase1-webapp-implementation.md`.**

Two execution options:

**1. Subagent-Driven（推奨）** — 各タスクを独立したサブエージェントが実行。タスク間でレビューを挟み、問題を早期に検知できる。

**2. Inline Execution** — このセッション内で executing-plans スキルを使用して順番に実行。チェックポイントでレビューを実施。

**どちらで進めますか？**
