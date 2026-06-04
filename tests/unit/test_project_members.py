import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_add_member_as_owner(client: AsyncClient, auth_headers: dict) -> None:
    r = await client.post("/api/v1/projects", json={"name": "MemberTest"}, headers=auth_headers)
    assert r.status_code == 201
    project_id = r.json()["id"]
    r2 = await client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"user_id": "user-b", "role": "member"},
        headers=auth_headers,
    )
    assert r2.status_code == 201
    assert r2.json()["user_id"] == "user-b"


@pytest.mark.asyncio
async def test_list_members(client: AsyncClient, auth_headers: dict) -> None:
    r = await client.post("/api/v1/projects", json={"name": "ListMemberTest"}, headers=auth_headers)
    project_id = r.json()["id"]
    await client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"user_id": "user-c", "role": "member"},
        headers=auth_headers,
    )
    r2 = await client.get(f"/api/v1/projects/{project_id}/members", headers=auth_headers)
    assert r2.status_code == 200
    assert "user-c" in [m["user_id"] for m in r2.json()]


@pytest.mark.asyncio
async def test_remove_member(client: AsyncClient, auth_headers: dict) -> None:
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
    r = await client.get("/api/v1/projects", headers=auth_headers)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_create_project_with_members(client: AsyncClient, auth_headers: dict) -> None:
    r = await client.post(
        "/api/v1/projects",
        json={"name": "WithMembers", "member_ids": ["user-e", "user-f"]},
        headers=auth_headers,
    )
    assert r.status_code == 201
    project_id = r.json()["id"]
    r2 = await client.get(f"/api/v1/projects/{project_id}/members", headers=auth_headers)
    user_ids = [m["user_id"] for m in r2.json()]
    assert "user-e" in user_ids and "user-f" in user_ids
