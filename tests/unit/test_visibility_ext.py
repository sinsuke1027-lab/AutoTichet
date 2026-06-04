# tests/unit/test_visibility_ext.py
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_task_visibility_tag(task_client: AsyncClient, auth_headers: dict) -> None:
    """visibility=tag のタスクが作成できる。"""
    r = await task_client.post(
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
    task_client: AsyncClient, auth_headers: dict
) -> None:
    """visibility=project のタスクが作成できる。"""
    proj_r = await task_client.post(
        "/api/v1/projects", json={"name": "VisibilityProject"}, headers=auth_headers
    )
    project_id = proj_r.json()["id"]
    r = await task_client.post(
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
    task_client: AsyncClient, auth_headers: dict
) -> None:
    """visibility=tag で visibility_tag が未指定なら 422。"""
    r = await task_client.post(
        "/api/v1/tasks",
        json={"title": "Missing Tag", "visibility": "tag"},
        headers=auth_headers,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_visibility_project_requires_project_id(
    task_client: AsyncClient, auth_headers: dict
) -> None:
    """visibility=project で visibility_project_id が未指定なら 422。"""
    r = await task_client.post(
        "/api/v1/tasks",
        json={"title": "Missing Project", "visibility": "project"},
        headers=auth_headers,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_tag_visibility_task_list_returns_200(
    task_client: AsyncClient, auth_headers: dict
) -> None:
    """タスク一覧が 200 を返す。"""
    r = await task_client.get("/api/v1/tasks", headers=auth_headers)
    assert r.status_code == 200
