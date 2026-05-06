from unittest.mock import MagicMock, patch

import respx
from httpx import Response

from src.connectors.graph_api import GraphAPIClient
from src.connectors.teams_chat import TeamsChatConnector

BASE = "https://graph.microsoft.com/v1.0"


def _make_graph_client() -> GraphAPIClient:
    with patch("msal.ConfidentialClientApplication") as mock_app_cls:
        mock_app = MagicMock()
        mock_app.acquire_token_for_client.return_value = {"access_token": "test-token"}
        mock_app_cls.return_value = mock_app
        client = GraphAPIClient("tenant", "client_id", "secret")
    client._app = mock_app  # type: ignore[attr-defined]
    return client


@respx.mock
async def test_get_channel_messages() -> None:
    client = _make_graph_client()
    connector = TeamsChatConnector(client)
    respx.get(f"{BASE}/teams/team-1/channels/channel-1/messages").mock(
        return_value=Response(
            200,
            json={"value": [{"id": "msg-1", "body": {"content": "タスクあり"}}]},
        )
    )
    messages = await connector.get_channel_messages("team-1", "channel-1")
    assert len(messages) == 1
    assert messages[0]["id"] == "msg-1"


@respx.mock
async def test_get_teams_returns_list() -> None:
    client = _make_graph_client()
    connector = TeamsChatConnector(client)
    respx.get(f"{BASE}/teams").mock(
        return_value=Response(
            200,
            json={"value": [{"id": "team-1", "displayName": "開発チーム"}]},
        )
    )
    teams = await connector.get_teams()
    assert teams[0]["displayName"] == "開発チーム"


@respx.mock
async def test_get_channels_returns_list() -> None:
    client = _make_graph_client()
    connector = TeamsChatConnector(client)
    respx.get(f"{BASE}/teams/team-1/channels").mock(
        return_value=Response(
            200,
            json={"value": [{"id": "ch-1", "displayName": "一般"}]},
        )
    )
    channels = await connector.get_channels("team-1")
    assert channels[0]["id"] == "ch-1"
