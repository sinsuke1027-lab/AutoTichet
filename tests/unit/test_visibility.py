from unittest.mock import AsyncMock, MagicMock

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
    # leader は department_tags 一致ユーザー ID を DB 検索（3 回 execute）
    leader = TokenPayload(sub="l1", roles=["leader"], department_tags=["営業部"])
    dept_result = MagicMock()
    dept_result.scalars.return_value.all.return_value = ["user-x"]
    db = _db_with_results([dept_result, _empty_count(), _empty_list()])
    client = _make_app(leader, db)
    resp = client.get("/api/v1/tasks")
    assert resp.status_code == 200


def test_leader_without_dept_tags_list_tasks_returns_200() -> None:
    # department_tags が空の leader は visibility=="all" のみ（2 回 execute）
    leader = TokenPayload(sub="l2", roles=["leader"], department_tags=[])
    db = _db_with_results([_empty_count(), _empty_list()])
    client = _make_app(leader, db)
    resp = client.get("/api/v1/tasks")
    assert resp.status_code == 200
