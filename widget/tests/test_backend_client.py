import pytest
from unittest.mock import MagicMock, patch


def _make_response(json_data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        import httpx
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    return resp


def test_get_users_returns_user_info_list():
    from widget.clients.backend_client import BackendClient, UserInfo
    raw = [
        {"user_id": "u1", "display_name": "山田 太郎", "role": "member"},
        {"user_id": "u2", "display_name": "田中 花子", "role": "admin"},
    ]
    with patch("httpx.get", return_value=_make_response(raw)):
        client = BackendClient("https://example.hf.space", "u1")
        users = client.get_users()
    assert len(users) == 2
    assert users[0] == UserInfo(user_id="u1", display_name="山田 太郎")
    assert users[1] == UserInfo(user_id="u2", display_name="田中 花子")


def test_get_projects_returns_project_info_list():
    from widget.clients.backend_client import BackendClient, ProjectInfo
    raw = [
        {"id": "p1", "name": "総務業務管理"},
        {"id": "p2", "name": "人事業務管理"},
    ]
    with patch("httpx.get", return_value=_make_response(raw)):
        client = BackendClient("https://example.hf.space", "u1")
        projects = client.get_projects()
    assert len(projects) == 2
    assert projects[0] == ProjectInfo(id="p1", name="総務業務管理")


def test_create_task_sends_correct_payload():
    from widget.clients.backend_client import BackendClient
    mock_resp = _make_response({"id": "task-uuid", "title": "テスト"})
    with patch("httpx.post", return_value=mock_resp) as mock_post:
        client = BackendClient("https://example.hf.space", "u1")
        payload = {"title": "テスト", "priority": "medium", "source_type": "manual"}
        result = client.create_task(payload)
    call_kwargs = mock_post.call_args
    assert call_kwargs.kwargs["headers"]["X-Dev-User"] == "u1"
    assert call_kwargs.kwargs["json"]["title"] == "テスト"
    assert result["id"] == "task-uuid"


def test_get_projects_handles_paginated_response():
    from widget.clients.backend_client import BackendClient
    raw = {"items": [{"id": "p1", "name": "プロジェクトA"}], "total": 1}
    with patch("httpx.get", return_value=_make_response(raw)):
        client = BackendClient("https://example.hf.space", "u1")
        projects = client.get_projects()
    assert projects[0].name == "プロジェクトA"
