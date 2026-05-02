from datetime import date
from unittest.mock import MagicMock, patch

import pytest
import respx
from httpx import Response

from src.connectors.graph_api import GraphAPIClient
from src.connectors.planner import PlannerConnector
from src.connectors.todo import TodoConnector
from src.models.task import ExtractedTask

BASE = "https://graph.microsoft.com/v1.0"


def _make_graph_client() -> GraphAPIClient:
    with patch("msal.ConfidentialClientApplication") as mock_app_cls:
        mock_app = MagicMock()
        mock_app.acquire_token_for_client.return_value = {"access_token": "test-token"}
        mock_app_cls.return_value = mock_app
        client = GraphAPIClient("tenant", "client_id", "secret")
    client._app = mock_app  # type: ignore[attr-defined]
    return client


def _task(
    visibility: str = "private",
    priority: str = "medium",
    assignee_user_id: str | None = "user-1",
    deadline: date | None = None,
) -> ExtractedTask:
    return ExtractedTask(
        is_task=True,
        title="テスト起票",
        visibility=visibility,  # type: ignore[arg-type]
        priority=priority,  # type: ignore[arg-type]
        assignee_user_id=assignee_user_id,
        deadline=deadline,
        confidence_score=0.9,
        source_type="email",
        source_id="msg-001",
    )


# ───────────────────────────── GraphAPIClient ──────────────────────────────


def test_get_token_raises_on_error() -> None:
    client = _make_graph_client()
    client._app.acquire_token_for_client.return_value = {  # type: ignore[attr-defined]
        "error": "invalid_client",
        "error_description": "Invalid credentials",
    }
    with pytest.raises(RuntimeError, match="トークン取得失敗"):
        client._get_token()


@respx.mock
async def test_get_unread_emails() -> None:
    client = _make_graph_client()
    respx.get(f"{BASE}/users/user-1/messages").mock(
        return_value=Response(
            200,
            json={"value": [{"id": "msg-1", "subject": "テスト"}]},
        )
    )
    emails = await client.get_unread_emails("user-1")
    assert len(emails) == 1
    assert emails[0]["subject"] == "テスト"


@respx.mock
async def test_mark_email_read() -> None:
    client = _make_graph_client()
    respx.patch(f"{BASE}/users/user-1/messages/msg-1").mock(return_value=Response(200, json={}))
    await client.mark_email_read("user-1", "msg-1")


@respx.mock
async def test_get_users() -> None:
    client = _make_graph_client()
    respx.get(f"{BASE}/users").mock(
        return_value=Response(
            200,
            json={"value": [{"id": "u1", "displayName": "山田太郎", "mail": "yamada@example.com"}]},
        )
    )
    users = await client.get_users()
    assert users[0]["displayName"] == "山田太郎"


@respx.mock
async def test_get_groups() -> None:
    client = _make_graph_client()
    respx.get(f"{BASE}/groups").mock(
        return_value=Response(200, json={"value": [{"id": "g1", "displayName": "営業部"}]})
    )
    groups = await client.get_groups()
    assert groups[0]["displayName"] == "営業部"


# ───────────────────────────── PlannerConnector ────────────────────────────


@respx.mock
async def test_planner_create_task_returns_id() -> None:
    client = _make_graph_client()
    connector = PlannerConnector(client)
    respx.post(f"{BASE}/planner/tasks").mock(
        return_value=Response(201, json={"id": "planner-task-1"})
    )
    task_id = await connector.create_task(_task(visibility="team"), plan_id="plan-abc")
    assert task_id == "planner-task-1"


@respx.mock
async def test_planner_create_task_with_deadline() -> None:
    client = _make_graph_client()
    connector = PlannerConnector(client)
    route = respx.post(f"{BASE}/planner/tasks").mock(
        return_value=Response(201, json={"id": "planner-task-2"})
    )
    task = _task(visibility="all", deadline=date(2026, 6, 30))
    await connector.create_task(task, plan_id="plan-all")
    assert route.called
    sent = route.calls.last.request
    import json

    body = json.loads(sent.content)
    assert body["dueDateTime"] == "2026-06-30T00:00:00Z"


# ───────────────────────────── TodoConnector ───────────────────────────────


@respx.mock
async def test_todo_create_task_uses_existing_list() -> None:
    client = _make_graph_client()
    connector = TodoConnector(client)
    respx.get(f"{BASE}/users/user-1/todo/lists").mock(
        return_value=Response(
            200,
            json={"value": [{"id": "list-1", "displayName": "AutoTicket"}]},
        )
    )
    respx.post(f"{BASE}/users/user-1/todo/lists/list-1/tasks").mock(
        return_value=Response(201, json={"id": "todo-task-1"})
    )
    task_id = await connector.create_task(_task(), user_id="user-1")
    assert task_id == "todo-task-1"


@respx.mock
async def test_todo_create_list_when_not_found() -> None:
    client = _make_graph_client()
    connector = TodoConnector(client)
    respx.get(f"{BASE}/users/user-1/todo/lists").mock(
        return_value=Response(200, json={"value": []})
    )
    respx.post(f"{BASE}/users/user-1/todo/lists").mock(
        return_value=Response(201, json={"id": "list-new"})
    )
    respx.post(f"{BASE}/users/user-1/todo/lists/list-new/tasks").mock(
        return_value=Response(201, json={"id": "todo-task-2"})
    )
    task_id = await connector.create_task(_task(), user_id="user-1")
    assert task_id == "todo-task-2"


async def test_todo_create_task_raises_without_user_id() -> None:
    client = _make_graph_client()
    connector = TodoConnector(client)
    task = _task(assignee_user_id=None)
    with pytest.raises(ValueError, match="user_id"):
        await connector.create_task(task)
