"""
Unit test fixtures — in-memory SQLite DB + AsyncClient.

This conftest is intentionally scoped to `tests/unit/` only.
It provides:
  - `client`      : httpx.AsyncClient wired to the FastAPI app
  - `auth_headers`: X-Dev-User header that satisfies dev_mode auth
"""
import json
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON, MetaData, Table
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db.models import (
    Base,
    Project,
    ProjectMember,
    Section,
    Task,
    TaskAssignee,
    TaskTag,
    TaskWorkHour,
    UserProfile,
)

# ---------------------------------------------------------------------------
# In-memory SQLite engine (per test function)
#
# We cannot use Base.metadata.create_all directly because `user_profiles`
# contains a PostgreSQL-only JSONB column.  Instead we build a minimal
# SQLite-compatible metadata that covers only the tables used by the
# projects/members router.
# ---------------------------------------------------------------------------

_SQLITE_URL = "sqlite+aiosqlite:///:memory:"

# Tables required by the projects router (in dependency order)
_MEMBER_TEST_TABLES = [
    Project.__table__,
    ProjectMember.__table__,
]

# Tables required by the tasks router (in dependency order)
_TASK_TEST_TABLES = [
    Project.__table__,
    Section.__table__,
    Task.__table__,
    TaskTag.__table__,
    TaskWorkHour.__table__,
    TaskAssignee.__table__,
    ProjectMember.__table__,
]

# Tables required by scope tests (tasks + users + projects)
_SCOPE_TEST_TABLES = [
    Project.__table__,
    UserProfile.__table__,
    Section.__table__,
    Task.__table__,
    TaskTag.__table__,
    TaskWorkHour.__table__,
    TaskAssignee.__table__,
    ProjectMember.__table__,
]


def _sqlite_metadata(tables: list | None = None) -> MetaData:
    """Return a MetaData that contains only the requested tables,
    with any PostgreSQL-specific column types replaced by SQLite equivalents."""
    from sqlalchemy import Column, DateTime, Float, String, Text, UUID as SA_UUID
    from sqlalchemy.dialects.postgresql import JSONB

    target_tables = tables if tables is not None else _MEMBER_TEST_TABLES
    meta = MetaData()
    for src_table in target_tables:
        if src_table.name in meta.tables:
            continue  # skip already-registered tables
        cols: list[Column] = []  # type: ignore[type-arg]
        for col in src_table.columns:
            # Clone, replacing JSONB → JSON
            col_type = JSON() if isinstance(col.type, JSONB) else col.type
            cols.append(
                Column(
                    col.name,
                    col_type,
                    primary_key=col.primary_key,
                    nullable=col.nullable,
                    server_default=col.server_default,
                )
            )
        Table(src_table.name, meta, *cols)
    return meta


@pytest.fixture()
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a fresh in-memory SQLite session for each test."""
    engine = create_async_engine(_SQLITE_URL, echo=False)
    meta = _sqlite_metadata()
    async with engine.begin() as conn:
        await conn.run_sync(meta.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(meta.drop_all)
    await engine.dispose()


@pytest.fixture()
async def task_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a fresh in-memory SQLite session with tasks + projects tables."""
    engine = create_async_engine(_SQLITE_URL, echo=False)
    meta = _sqlite_metadata(tables=_TASK_TEST_TABLES)
    async with engine.begin() as conn:
        await conn.run_sync(meta.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(meta.drop_all)
    await engine.dispose()


# ---------------------------------------------------------------------------
# FastAPI app + AsyncClient wired to the in-memory DB
# ---------------------------------------------------------------------------


@pytest.fixture()
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient backed by the FastAPI app, with DB overridden to in-memory SQLite."""
    # Import here to avoid top-level side-effects (scheduler, etc.)
    from fastapi import FastAPI

    from src.api.auth import get_current_user
    from src.api.routers import projects
    from src.db.engine import get_db
    from src.models.config import Settings, get_settings

    # Override settings: dev_mode=True so X-Dev-User header works;
    # dummy DB URL so the real engine is never touched.
    test_settings = Settings(
        dev_mode=True,
        database_url=_SQLITE_URL,
    )

    app = FastAPI()
    app.include_router(projects.router)

    # Replace get_db with the fixture session
    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    # Patch get_settings so dev_mode=True is visible inside get_current_user
    with patch("src.api.auth.get_settings", return_value=test_settings), patch(
        "src.models.config.get_settings", return_value=test_settings
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac


@pytest.fixture()
async def task_client(task_db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient backed by the FastAPI app including tasks + projects routers."""
    from fastapi import FastAPI

    from src.api.routers import projects
    from src.api.routers import tasks_crud
    from src.db.engine import get_db
    from src.models.config import Settings

    test_settings = Settings(
        dev_mode=True,
        database_url=_SQLITE_URL,
    )

    app = FastAPI()
    app.include_router(projects.router)
    app.include_router(tasks_crud.router)

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield task_db_session

    app.dependency_overrides[get_db] = _override_get_db

    with patch("src.api.auth.get_settings", return_value=test_settings), patch(
        "src.models.config.get_settings", return_value=test_settings
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac


# ---------------------------------------------------------------------------
# Auth headers (dev-mode X-Dev-User)
# ---------------------------------------------------------------------------

_DEV_USER: dict[str, Any] = {
    "userId": "user-a",
    "displayName": "Test User A",
    "email": "user-a@example.com",
    "role": "member",
    "departmentTags": [],
}


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    """Return X-Dev-User header that dev_mode auth accepts."""
    return {"X-Dev-User": json.dumps(_DEV_USER)}


@pytest.fixture()
async def scope_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a fresh in-memory SQLite session with tasks + users + projects tables."""
    engine = create_async_engine(_SQLITE_URL, echo=False)
    meta = _sqlite_metadata(tables=_SCOPE_TEST_TABLES)
    async with engine.begin() as conn:
        await conn.run_sync(meta.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(meta.drop_all)
    await engine.dispose()


@pytest.fixture()
async def scope_client(scope_db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient with tasks + users + projects routers for scope filter tests."""
    from fastapi import FastAPI

    from src.api.routers import projects, tasks_crud, users
    from src.db.engine import get_db
    from src.models.config import Settings

    test_settings = Settings(
        dev_mode=True,
        database_url=_SQLITE_URL,
    )

    app = FastAPI()
    app.include_router(projects.router)
    app.include_router(tasks_crud.router)
    app.include_router(users.router)

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield scope_db_session

    app.dependency_overrides[get_db] = _override_get_db

    with patch("src.api.auth.get_settings", return_value=test_settings), patch(
        "src.models.config.get_settings", return_value=test_settings
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac
