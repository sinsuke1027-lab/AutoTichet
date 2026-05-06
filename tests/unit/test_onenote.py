from unittest.mock import MagicMock, patch

import respx
from httpx import Response

from src.connectors.graph_api import GraphAPIClient
from src.connectors.onenote import OneNoteConnector

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
async def test_get_notebooks_returns_list() -> None:
    client = _make_graph_client()
    connector = OneNoteConnector(client)
    respx.get(f"{BASE}/me/onenote/notebooks").mock(
        return_value=Response(
            200,
            json={"value": [{"id": "nb-1", "displayName": "会議メモ"}]},
        )
    )
    notebooks = await connector.get_notebooks()
    assert notebooks[0]["displayName"] == "会議メモ"


@respx.mock
async def test_get_recent_pages_returns_list() -> None:
    client = _make_graph_client()
    connector = OneNoteConnector(client)
    respx.get(f"{BASE}/me/onenote/pages").mock(
        return_value=Response(
            200,
            json={"value": [{"id": "pg-1", "title": "2026-05-07 議事録"}]},
        )
    )
    pages = await connector.get_recent_pages(count=10)
    assert pages[0]["id"] == "pg-1"


@respx.mock
async def test_get_page_content_returns_html() -> None:
    client = _make_graph_client()
    connector = OneNoteConnector(client)
    respx.get(f"{BASE}/me/onenote/pages/page-1/content").mock(
        return_value=Response(200, text="<html>タスクあり</html>")
    )
    content = await connector.get_page_content("page-1")
    assert "タスクあり" in content
