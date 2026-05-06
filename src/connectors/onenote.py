from typing import Any

import httpx

from src.connectors.graph_api import GraphAPIClient


class OneNoteConnector:
    """OneNote ページ取得コネクター（Graph API 経由）"""

    BASE_URL = "https://graph.microsoft.com/v1.0"

    def __init__(self, graph_client: GraphAPIClient) -> None:
        self._graph = graph_client

    async def get_notebooks(self) -> list[dict[str, Any]]:
        """ノートブック一覧を取得する"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/me/onenote/notebooks",
                headers=self._graph._headers(),
                params={"$select": "id,displayName,lastModifiedDateTime"},
            )
            resp.raise_for_status()
            return list(resp.json().get("value", []))

    async def get_recent_pages(self, count: int = 20) -> list[dict[str, Any]]:
        """最近更新されたページ一覧を取得する"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/me/onenote/pages",
                headers=self._graph._headers(),
                params={
                    "$select": "id,title,lastModifiedDateTime",
                    "$orderby": "lastModifiedDateTime desc",
                    "$top": str(count),
                },
            )
            resp.raise_for_status()
            return list(resp.json().get("value", []))

    async def get_page_content(self, page_id: str) -> str:
        """ページの HTML コンテンツを取得する"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/me/onenote/pages/{page_id}/content",
                headers=self._graph._headers(),
            )
            resp.raise_for_status()
            return resp.text
